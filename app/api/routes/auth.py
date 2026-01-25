import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.dependency import TokenDep
from app.api.rbac import UserApiDep
from app.models.api import GeneratedToken, StandardResponse
from app.token.payload import TokenData
from app.token.token_manager import KeyNotFoundError, SigningKeyExpired

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authorization Token"])


@router.get(
    "/token/generate",
    response_model=StandardResponse[GeneratedToken],
    status_code=status.HTTP_201_CREATED,
    summary="generate a new jwt token",
)
async def generate_token(
    token_manager: TokenDep,
    payload: UserApiDep,
):
    try:
        data = TokenData(
            user_id=payload.user_id,
            role=payload.role,
        )

        token = token_manager.create_access_token(payload_data=data)

        return StandardResponse(
            message="successfully generated the token",
            data=GeneratedToken(
                token=token,
            ),
        )
    except KeyNotFoundError as e:
        logger.exception(f"key not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="signing key not found to generate token",
        )
    except SigningKeyExpired as e:
        logger.exception(f"signing key expired: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="signing key expired for generating token",
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"error generating token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error generating token",
        )
