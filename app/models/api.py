from pydantic import BaseModel, EmailStr, Field
from typing import Generic, TypeVar, Optional, List
from app.database.schema import Role

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    message: str
    data: Optional[T] = None


class UserClientBase(BaseModel):
    email: EmailStr
    role: Role


class RegisterUser(BaseModel):
    email: EmailStr


class IndividualUser(BaseModel):
    id: int
    email: str
    role: Role


class ListOfUsers(BaseModel):
    users: List[IndividualUser]


class GeneratedToken(BaseModel):
    token: str

class UploadedDataset(BaseModel):
    upload_token: str
    filename: str
    size: int

class LogEntry(BaseModel):
    timestamp: str
    level: str
    logger: str
    message: str
    module: str
    line_no: int
    thread_id: Optional[str] = None
    exception: Optional[str] = None
