from pydantic import BaseModel
from app.database.schema import Role
from app.models.api import UserClientBase


class VerifiedApiKey(BaseModel):
    id: int
    user_id: int
    user_role: Role
    key_id: int
    key_credential: bytes
    key_signature: bytes


class UserClientCreate(UserClientBase):
    pass


class ApiKeyCreate(BaseModel):
    key_id: int
    key_credential: bytes
    key_signature: bytes


class StoreApiKey(ApiKeyCreate):
    user_id: int


class CreateUploadRecord(BaseModel):
    upload_token: str
    file_path: str
    filename: str
    file_size: str

class AssociateUploadThread(BaseModel):
    token: str
    thread_id: str