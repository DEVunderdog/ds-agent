import tempfile
import uuid
from pathlib import Path

import magic
import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.dependency import DbDep
from app.api.rbac import UserTokenDep
from app.constants.globals import MAX_DATASET_FILE_SIZE
from app.database.uploads import create_upload
from app.models.api import StandardResponse, UploadedDataset
from app.models.database import CreateUploadRecord

logger = structlog.get_logger(__name__)

MAX_FILE_SIZE = MAX_DATASET_FILE_SIZE * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

router = APIRouter(prefix="/uploads", tags=["file uploads"])


@router.post(
    "/dataset",
    respponse_model=StandardResponse[UploadedDataset],
    status_code=status.HTTP_201_CREATED,
    summary="upload a dataset",
)
async def upload_dataset(
    db: DbDep,
    payload: UserTokenDep,
    file: UploadFile = File(...),
):

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid file extension. Only .csv files are allowed",
        )

    temp_file_path = None
    upload_successful = False

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
            temp_file_path = temp_file.name
            real_file_size = 0

            while content := await file.read(CHUNK_SIZE):
                real_file_size += len(content)

                if real_file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"file too large. Maximum size is {MAX_FILE_SIZE/1024/1024}MB",
                    )

                temp_file.write(content)

            temp_file.seek(0)

            header_sample = temp_file.read(2048)
            mime_type = magic.from_buffer(header_sample, mime=True)

            if mime_type not in ["text/csv", "text/plain", "application/csv"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"invalid file type detected: {mime_type}",
                )

            upload_token = str(uuid.uuid4())

            args = CreateUploadRecord(
                upload_token=upload_token,
                file_path=temp_file_path,
                filename=file.filename,
                file_size=real_file_size,
            )

            await create_upload(
                db=db,
                params=args,
            )

            upload_successful = True

            return StandardResponse(
                message="successfully uploaded a dataset",
                data=UploadedDataset(
                    upload_token=upload_token,
                    filename=file.filename,
                    size=real_file_size,
                ),
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"error while uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error while uploading file",
        )

    finally:
        if not upload_successful and temp_file_path:
            Path(temp_file_path).unlink(missing_ok=True)
