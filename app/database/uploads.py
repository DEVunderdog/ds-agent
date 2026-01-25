import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.schema import DatasetUpload
from app.models.database import AssociateUploadThread, CreateUploadRecord

logger = structlog.get_logger(__name__)


class UploadNotFound(Exception):
    pass


async def create_upload(
    *,
    db: AsyncSession,
    params: CreateUploadRecord,
):
    try:
        upload = DatasetUpload(
            upload_token=params.upload_token,
            filename=params.filename,
            file_path=params.file_path,
            file_size=params.file_size,
        )

        db.add(upload)
        await db.commit()

    except Exception as e:
        await db.rollback()
        raise RuntimeError("failed to create upload") from e


async def associate_with_thread(
    *,
    db: AsyncSession,
    params: AssociateUploadThread,
) -> Optional[str]:
    try:
        stmt = (
            update(DatasetUpload)
            .where(
                DatasetUpload.upload_token == params.token,
                DatasetUpload.is_active == True,
                DatasetUpload.thread_id.is_(None),
            )
            .values(
                thread_id=params.thread_id,
                associated_at=datetime.now(timezone.utc),
            )
            .returning(
                DatasetUpload.file_path,
            )
        )

        result = await db.execute(stmt)

        file_path = result.scalar_one_or_none()

        if not file_path:
            raise UploadNotFound("upload not found")

        await db.commit()

        return file_path

    except Exception:
        await db.rollback()
        raise


async def get_dataset_path(
    *,
    db: AsyncSession,
    thread_id: str,
) -> Optional[str]:
    stmt = select(DatasetUpload.file_path).where(
        DatasetUpload.thread_id == thread_id,
        DatasetUpload.is_active == True,
    )

    result = await db.execute(stmt)

    file_path = result.scalar_one_or_none()

    if not file_path:
        raise UploadNotFound("upload not found")

    return file_path


async def _remove_file_asynchronously(path_str: str):
    path = Path(path_str)
    if await asyncio.to_thread(path.exists):
        await asyncio.to_thread(path.unlink)


async def cleanup_orphaned_uploads(*, db: AsyncSession, max_age_hours: int = 24) -> int:
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        stmt = select(DatasetUpload).where(
            DatasetUpload.uploaded_at < cutoff,
            or_(
                (DatasetUpload.is_active == True) & (DatasetUpload.thread_id.is_(None)),
                DatasetUpload.is_active == False,
            ),
        )

        result = await db.execute(stmt)

        uploads_to_clean = result.scalars().all()

        if not uploads_to_clean:
            return

        for upload in uploads_to_clean:
            try:
                await _remove_file_asynchronously(upload.file_path)
            except OSError as e:
                logger.exception(f"error while unlinking temps: {e}")

            if upload.is_active:
                upload.is_active = False

        await db.commit()

    except Exception:
        await db.rollback()
        raise
