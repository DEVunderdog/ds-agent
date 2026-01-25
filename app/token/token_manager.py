import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta
from typing import Dict, Optional, Tuple

import jwt
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.connection import db_session
from app.database.encryption_key import get_active_encryption_key
from app.token.key_info import KeyInfo
from app.token.payload import TokenData
from app.utils.application_timezone import get_current_time

logger = structlog.get_logger(__name__)


class KeyNotFoundError(Exception):
    pass


class SigningKeyExpired(Exception):
    pass


class NotFoundApiKey(Exception):
    pass


class SigningKeyNotFoundError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


class TokenManager:
    def __init__(self):
        self._active_key_config: Optional[Tuple[Dict[int, KeyInfo], int]] = None
        self.token_algorithm = "HS256"

    @classmethod
    async def create(
        cls,
    ) -> "TokenManager":

        instance = cls()

        async with db_session() as db:
            instance._active_key_config = await instance._build_active_key(db=db)

            if instance._active_key_config is None:
                raise RuntimeError(
                    "failed to initialize TokenManager with encryption keys",
                )

            return instance

    async def _build_active_key(
        self,
        db: AsyncSession,
    ) -> Tuple[Dict[int, KeyInfo], int]:
        active_encryption_key = await get_active_encryption_key(db=db)
        active_id: Optional[int] = None
        key_info: Dict[int, KeyInfo] = {}

        if active_encryption_key is None:
            raise SigningKeyNotFoundError("cannot find the active signing keys")

        active_id = active_encryption_key.id
        key_info[active_id] = KeyInfo(
            key=active_encryption_key.symmetric_key,
            expires_at=active_encryption_key.expired_at,
        )

        return (key_info, active_id)

    def _get_keys(self) -> Tuple[Dict[int, KeyInfo], int]:
        return self._active_key_config

    def create_access_token(
        self,
        payload_data: TokenData,
    ) -> str:
        all_keys, active_key_id = self._get_keys()
        if active_key_id not in all_keys:
            raise KeyNotFoundError(
                "active key id not found in current key configuration",
            )

        active_key_info = all_keys[active_key_id]
        if active_key_info.is_expired():
            raise SigningKeyExpired("signing key is expired")

        to_encode = payload_data.model_dump(mode="json", exclude_unset=True)

        current_time = get_current_time()

        expiry = current_time + timedelta(
            hours=settings.JWT_ACCESS_TOKEN_HOURS,
        )

        to_encode.update(
            {
                "exp": int(expiry.timestamp()),
                "iss": settings.JWT_ISSUER,
                "aud": settings.JWT_AUDIENCE,
                "iat": int(current_time.timestamp()),
                "nbf": int(current_time.timestamp()),
                "jti": str(uuid.uuid4()),
            }
        )

        headers = {"kid": str(active_key_id)}

        encoded_jwt = jwt.encode(
            to_encode,
            active_key_info.key,
            algorithm=self.token_algorithm,
            headers=headers,
        )

        return encoded_jwt

    def verify_token(self, token: str) -> Optional[TokenData]:
        try:
            unverified_headers = jwt.get_unverified_header(jwt=token)
            kid = unverified_headers.get("kid")

            if not kid:
                raise InvalidTokenError("token missing header")

            (all_keys, _) = self._get_keys()

            key_for_verification = all_keys.get(int(kid))
            if not key_for_verification:
                raise KeyNotFoundError(f"key id {kid} not found for verification")

            if key_for_verification.is_expired():
                raise SigningKeyExpired(
                    f"symmetric key {kid} for toekn verification has expired",
                )

            payload = jwt.decode(
                jwt=token,
                key=key_for_verification.key,
                algorithms=[self.token_algorithm],
                audience=settings.JWT_AUDIENCE,
                leeway=5,
                issuer=settings.JWT_ISSUER,
                options={
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                },
            )
            return TokenData(**payload)
        except jwt.ExpiredSignatureError:
            logger.exception("token has expired")
            raise
        except jwt.InvalidAudienceError:
            logger.exception("invalid token audience")
            raise
        except jwt.InvalidIssuerError:
            logger.exception("invalid token issuer")
            raise
        except jwt.DecodeError as e:
            logger.exception(f"token decode error: {e}")
            raise
        except jwt.InvalidTokenError as e:
            logger.exception(f"invalid token: {e}")
            raise
        except Exception as e:
            logger.exception(f"invalid token: {e}")
            raise

    def generate_api_key(self) -> Tuple[str, bytes, bytes, int]:
        all_keys, active_key_id = self._get_keys()

        random_bytes = secrets.token_bytes(24)
        random_bytes_b64 = base64.urlsafe_b64encode(random_bytes).decode("utf-8")

        active_key_info = all_keys.get(active_key_id)
        if not active_key_info:
            raise KeyNotFoundError(f"key id {active_key_id} not found for verification")

        if active_key_info.is_expired():
            raise SigningKeyExpired(f"key_id {active_key_id} has been expired")

        data_to_hmac = f"{active_key_id}:{random_bytes_b64}".encode("utf-8")
        hmac_obj = hmac.new(active_key_info.key, data_to_hmac, hashlib.sha256)
        signature_bytes = hmac_obj.digest()

        signature_b64 = base64.urlsafe_b64encode(signature_bytes).decode("utf-8")

        api_key = f"{random_bytes_b64}.{signature_b64}"

        api_key_bytes = api_key.encode("utf-8")

        return (api_key, api_key_bytes, signature_bytes, active_key_id)

    def verify_api_key(self, api_key: str, kid: int) -> bool:
        parts = api_key.split(".")
        if len(parts) != 2:
            return False

        random_bytes_b64, signature_b64 = parts
        all_keys, _ = self._get_keys()

        key_info = all_keys.get(kid)
        if not key_info:
            logger.info("cannot find key information while verifying the api key")
            return False

        if key_info.is_expired():
            raise SigningKeyExpired(
                f"symmetric key {kid} for token verification has expired",
            )

        data_to_hmac = f"{kid}: {random_bytes_b64}".encode("utf-8")

        expected_hmac_obj = hmac.new(key_info.key, data_to_hmac, hashlib.sha256)
        expected_signature_bytes = expected_hmac_obj.digest()

        try:
            client_signature_bytes = base64.urlsafe_b64decode(signature_b64)
        except Exception as e:
            logger.exception(
                f"error while decoding signature and providing key hmac: {e}"
            )
            return False

        return hmac.compare_digest(
            expected_signature_bytes,
            client_signature_bytes,
        )
