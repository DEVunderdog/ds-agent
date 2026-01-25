from typing import List

import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.dependency import DbDep
from app.api.rbac import AdminTokenDep
from app.database.api_key import fetch_user_api_key
from app.database.user import delete_user_db, list_users_db, promote_user_db
from app.mail.send_mail import send_api_key_mail
from app.models.api import IndividualUser, ListOfUsers, StandardResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/list",
    response_model=StandardResponse[ListOfUsers],
    status_code=status.HTTP_200_OK,
    summary="list of users",
)
async def list_users(
    payload: AdminTokenDep,
    db: DbDep,
    limit: int = 10,
    offset: int = 0,
):
    try:
        users: List[IndividualUser] = []
        db_users = await list_users_db(
            db=db,
            limit=limit,
            offset=offset,
        )

        if db_users is not None:
            for user in db_users:
                item = IndividualUser(
                    id=user.id,
                    email=user.email,
                    role=user.role,
                )
                users.append(item)

        return StandardResponse(
            message="successfully listed users", data=ListOfUsers(users=users)
        )

    except Exception as e:
        logger.exception(f"error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error listing users",
        )


@router.patch(
    "/promote/{user_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="promote user to admin",
)
async def promote_user(
    user_id: int,
    payload: AdminTokenDep,
    db: DbDep,
):
    try:
        user = await promote_user_db(
            db=db,
            user_id=user_id,
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot find user with provided email",
            )

        return StandardResponse(
            message="successfully promoted user",
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"error promoting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error promoting user",
        )


@router.delete(
    "/delete/{user_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="deletion of user",
)
async def delete_users(
    user_id: int,
    db: DbDep,
    payload: AdminTokenDep,
):
    try:
        if payload.user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="you cannot deletet yourself",
            )

        deleted = await delete_user_db(
            db=db,
            user_id=user_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot find user with provided id",
            )

        return StandardResponse(
            message="successfully deleted user",
        )

    except HTTPException:
        raise

    except Exception as e:
        msg = "error deleting user"
        logger.exception(f"{msg}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=msg,
        )


@router.get(
    "/fetch-keys/{user_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="fetch any user api keys",
)
async def send_keys_to_user(
    user_id: int,
    db: DbDep,
    payload: AdminTokenDep,
):
    try:
        api_key, email = fetch_user_api_key(
            db=db,
            user_id=user_id,
        )

        if api_key is None:
            logger.exception("not found api key")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="error fetching api keys",
            )

        send_api_key_mail(
            email_to=email,
            api_key=api_key,
        )

        return StandardResponse(
            message="successfully send api keys via email",
        )

    except HTTPException:
        raise

    except Exception as e:
        msg = "error fetching api keys"
        logger.exception(f"{msg}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=msg,
        )
