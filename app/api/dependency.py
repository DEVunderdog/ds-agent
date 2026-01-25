from fastapi import Depends, Request, HTTPException, status, Header
from fastapi.security import HTTPBearer, APIKeyHeader
from typing import Annotated, Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from jwt import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    DecodeError,
    InvalidTokenError,
)
from app.database.connection import get_db
from app.token.token_manager import (
    TokenManager,
    KeyNotFoundError,
    SigningKeyExpired,
    TokenData,
)
from app.token.payload import ApiData
from app.constants.globals import TOKEN_MANAGER_STATE
from app.database.api_key import get_api_key_for_verification
from app.service.chat_service import ChatService

oauth2_scheme = HTTPBearer(auto_error=False)

api_key_scheme = APIKeyHeader(
    name="Authorization",
    auto_error=False,
    scheme_name="ApiKeyAuth",
    description="enter API Key in the format: ApiKey <API KEY>",
)


def get_token_manager(request: Request) -> TokenManager:
    if not hasattr(request.app.state, TOKEN_MANAGER_STATE):
        raise RuntimeError("TokenManager not initialized, check lifespan events")
    return request.app.state.token_manager


TokenDep = Annotated[TokenManager, Depends(get_token_manager)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_token_payload(
    token: Annotated[Optional[str], Depends(oauth2_scheme)],
    token_manager: TokenDep,
) -> TokenData:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated; missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_str = token.credentials
    try:
        payload = token_manager.verify_token(token=token_str)

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid token payload",
            )

        return payload
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="invalid token"'
            },
        )
    except KeyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="cannot find signing key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except SigningKeyExpired:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="signing key expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token has expired",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="the token has expired"'
            },
        )
    except InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid audience in token",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="the token audience is invalid"',
            },
        )
    except InvalidIssuerError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid issuer in token",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="the token issuer is invalid"',
            },
        )
    except DecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error decoding token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="the token is invalid"'
            },
        )

    except HTTPException as e:
        raise e

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error while verifying token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_api_payload(
    db: DbDep,
    token_manager: TokenDep,
    authorization: Annotated[
        Optional[str], Header(alias="Authorization", convert_underscores=False)
    ] = None,
) -> Optional[ApiData]:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated: missing authorization header for api key",
        )

    auth_parts = authorization.split(" ", 1)
    if len(auth_parts) != 2 or auth_parts[0] != "ApiKey":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid api key authentication scheme. Expected 'ApiKey <API KEY>'",
        )

    api_key_full_string = auth_parts[1]
    api_key_bytes = api_key_full_string.encode("utf-8")

    verified_api_key = await get_api_key_for_verification(db=db, api_key=api_key_bytes)
    if not verified_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="api key not found",
        )

    try:
        is_valid = token_manager.verify_api_key(
            api_key=api_key_full_string,
            kid=verified_api_key.key_id,
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="api key verification failed: signature mismatched",
            )

        return ApiData(
            user_id=verified_api_key.user_id,
            api_key_id=verified_api_key.id,
            role=verified_api_key.user_role,
        )

    except SigningKeyExpired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="signing key expired, error verifying api key",
        )

    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="signing key expired, error verifying api key",
        )

    except HTTPException as e:
        raise e

    except HTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"internal server error while verifying api key: {e}",
        )


TokenPayloadDep = Annotated[TokenDep, Depends(get_token_payload)]
ApiPayloadDep = Annotated[ApiData, Depends(get_api_payload)]


def get_chat_service(request: Request) -> ChatService:
    agent_graph = request.app.state.agent_graph

    return ChatService(agent_graph)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
