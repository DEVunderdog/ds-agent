from typing import List, TypeVar, Annotated
from fastapi import HTTPException, status, Depends
from app.database.schema import Role
from app.api.dependency import TokenPayloadDep, ApiPayloadDep
from app.token.payload import PayloadData, TokenData, ApiData

T = TypeVar("T", bound=PayloadData)


class BaseRoleChecker:
    def __init__(self, allowed_roles: List[Role]):
        self.allowed_roles = allowed_roles

    def verify(self, payload: T) -> T:
        if payload.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient permissions to perform this action",
            )
        return payload


class CheckTokenRole(BaseRoleChecker):
    def __call__(self, payload: TokenPayloadDep):
        return self.verify(payload=payload)


class CheckApiRole(BaseRoleChecker):
    def __call__(self, payload: ApiPayloadDep):
        return self.verify(payload=payload)


AdminTokenDep = Annotated[TokenData, Depends(CheckTokenRole([Role.USER]))]
AdminApiDep = Annotated[ApiData, Depends(CheckApiRole([Role.ADMIN]))]

UserTokenDep = Annotated[TokenData, Depends(CheckTokenRole([Role.ADMIN, Role.USER]))]
UserApiDep = Annotated[ApiData, Depends(CheckApiRole([Role.ADMIN, Role.USER]))]
