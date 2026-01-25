from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy import select
from app.models.database import VerifiedApiKey
from app.database.schema import User, ApiKey


async def get_api_key_for_verification(
    *,
    db: AsyncSession,
    api_key: bytes,
) -> VerifiedApiKey:
    u = aliased(User)

    stmt = (
        select(ApiKey, u.role.label("role"))
        .join(u, ApiKey.user)
        .where(ApiKey.key_credential == api_key)
    )

    result = await db.execute(stmt)

    row = result.first()

    if not row:
        return None

    api_key_obj, role = row

    return VerifiedApiKey(
        id=api_key_obj.id,
        user_id=api_key_obj.user_id,
        user_role=role,
        key_id=api_key_obj.key_id,
        key_credential=api_key_obj.key_credential,
        key_signature=api_key_obj.key_signature,
    )


async def fetch_user_api_key(
    *,
    db: AsyncSession,
    user_id: int,
) -> Optional[Tuple[str, str]]:

    stmt = (
        select(ApiKey.key_credential, User.email).join(User).where(User.id == user_id)
    )

    result = await db.execute(stmt)

    row = result.first()

    return row if row else None
