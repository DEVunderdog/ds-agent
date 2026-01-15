from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar("T")

class StandardResponse(BaseModel, Generic[T]):
    message: str
    data: Optional[T] = None
    