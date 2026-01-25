import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.dependency import DbDep, TokenManager
from app.api.rbac import UserTokenDep
from app.database.api_key import fetch_user_api_key
from app.database.schema import Role
from app.database.user import register_user
from app.mail.send_mail import send_api_key_mail
from app.models.api import RegisterUser, StandardResponse
from app.models.database import ApiKeyCreate, UserClientCreate

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/user", tags=["user management"])


@router.post(
    "/register",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="register a new user",
)
async def register_new_user(
    user_in: RegisterUser,
    db: DbDep,
    token_manager: TokenManager,
):
    try:
        api_key, api_key_bytes, api_key_signature, active_key_id = (
            token_manager.generate_api_key()
        )

        user_args = UserClientCreate(
            email=user_in.email,
            role=Role.USER,
        )
        api_key_args = ApiKeyCreate(
            key_id=active_key_id,
            key_credential=api_key_bytes,
            key_signature=api_key_signature,
        )

        user, _ = await register_user(
            db=db,
            user_params=user_args,
            api_key_params=api_key_args,
        )

        send_api_key_mail(email_to=[user.email], api_key=api_key)

        return StandardResponse(
            message="user registered successfully",
        )

    except Exception as e:
        logger.exception(f"error registering user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error registering user",
        )


@router.get(
    "/keys",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="fetch api keys",
)
async def fetch_api_keys(
    payload: UserTokenDep,
    db: DbDep,
):
    try:
        api_key, email = await fetch_user_api_key(
            db=db,
            user_id=payload.user_id,
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
