from pydantic import BaseModel, EmailStr
from typing import Generic, TypeVar, Optional
from app.database.schema import Role

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    message: str
    data: Optional[T] = None


class UserClientBase(BaseModel):
    email: EmailStr
    role: Role
