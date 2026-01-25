from typing import Optional, Dict, Any, Literal, Union, List
from pydantic import BaseModel, Field, field_validator
from enum import StrEnum


class GenerationEventType(StrEnum):
    METADATA = "metadata"
    TOKEN_EVENT = "token_event"
    TOOL_START_EVENT = "tool_start"
    TOOL_END_EVENT = "tool_end"
    DONE_EVENT = "done"
    ERROR_EVENT = "error"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: Optional[str] = Field(None, description="conversational thread id")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    upload_token: Optional[str] = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message cannot be empty or whitespace")
        return v.strip()


class EventMetadata(BaseModel):
    thread_id: str


class TokenEvent(BaseModel):
    content: str
    thread_id: str


class ToolStartEvent(BaseModel):
    tool: str
    thread_id: str


class ToolEndEvent(BaseModel):
    tool: str
    output: str
    thread_id: str


class DoneEvent(BaseModel):
    thread_id: str
    status: str


class ErrorEvent(BaseModel):
    thread_id: str
    error: Any


class MetadataGeneratedEvent(BaseModel):
    event: Literal[GenerationEventType.METADATA]
    data: EventMetadata


class TokenGeneratedEvent(BaseModel):
    event: Literal[GenerationEventType.TOKEN_EVENT]
    data: TokenEvent


class ToolStartGeneratedEvent(BaseModel):
    event: Literal[GenerationEventType.TOOL_START_EVENT]
    data: ToolStartEvent


class ToolEndGeneratedEvent(BaseModel):
    event: Literal[GenerationEventType.TOOL_END_EVENT]
    data: ToolEndEvent


class DoneGeneratedEvent(BaseModel):
    event: Literal[GenerationEventType.DONE_EVENT]
    data: DoneEvent


class ErrorGeneratedEvent(BaseModel):
    event: Literal[GenerationEventType.ERROR_EVENT]
    data: ErrorEvent


GeneratedEvent = Union[
    MetadataGeneratedEvent,
    TokenGeneratedEvent,
    ToolStartGeneratedEvent,
    ToolEndGeneratedEvent,
    DoneGeneratedEvent,
    ErrorGeneratedEvent,
]


class HistoryMessages(BaseModel):
    type: str
    content: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    tool_call_id: Optional[str] = None


class HistoryResponse(BaseModel):
    thread_id: str
    messages: List[HistoryMessages]
