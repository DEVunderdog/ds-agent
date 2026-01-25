from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

import structlog
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.orchestrator.state import AgentState
from app.database.uploads import UploadNotFound, associate_with_thread
from app.models.database import AssociateUploadThread
from app.models.service import (
    ChatRequest,
    DoneEvent,
    DoneGeneratedEvent,
    ErrorEvent,
    ErrorGeneratedEvent,
    EventMetadata,
    GenerationEventType,
    HistoryMessages,
    MetadataGeneratedEvent,
    TokenEvent,
    TokenGeneratedEvent,
    ToolEndEvent,
    ToolEndGeneratedEvent,
    ToolStartEvent,
    ToolStartGeneratedEvent,
)

logger = structlog.get_logger(__name__)


class ChatService:
    def __init__(
        self,
        agent_graph: CompiledStateGraph,
        db: Callable[[], AsyncGenerator[AsyncSession, None]],
    ):
        self.agent_graph = agent_graph
        self.db = db

    @asynccontextmanager
    async def _get_db(self) -> AsyncGenerator[AsyncSession, None]:
        async for session in self.db:
            yield session

    async def _handle_upload_association(
        self,
        upload_token: str,
        thread_id: str,
    ) -> Optional[str]:
        async with self._get_db() as db_session:
            try:
                file_path = await associate_with_thread(
                    db=db_session,
                    params=AssociateUploadThread(
                        token=upload_token,
                        thread_id=thread_id,
                    ),
                )

                return file_path
            except UploadNotFound:
                logger.warning(
                    "upload token not found or already associated",
                )
                raise
            except Exception as e:
                logger.exception(
                    "error associating upload",
                    upload_token=upload_token,
                    error=str(e),
                )
                raise

    def _build_config(
        self,
        thread_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        if metadata:
            config["metadata"] = metadata

        return config

    def _prepare_state(
        self,
        message: str,
        dataset_path: Optional[str] = None,
    ) -> AgentState:
        state = {"messages": [HumanMessage(content=message)]}

        if dataset_path is not None:
            state["dataset_path"] = dataset_path

        return state

    def _extract_text_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                elif hasattr(part, "type") and getattr(part, "type") == "text":
                    text_parts.append(getattr(part, "text", ""))

            return "".join(text_parts)

        return str(content)

    async def generate_response(
        self,
        request: ChatRequest,
        thread_id: str,
        is_new_conversation: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            logger.info("starting generation loop for input")

            dataset_path = None

            if is_new_conversation and request.upload_token:
                logger.info("new conversation with upload token initiated")

                dataset_path = await self._handle_upload_association(
                    upload_token=request.upload_token,
                    thread_id=thread_id,
                )

                if not dataset_path:
                    logger.exception(
                        "failed to associate upload",
                    )
                    yield ErrorGeneratedEvent(
                        event=GenerationEventType.ERROR_EVENT,
                        data=ErrorEvent(
                            thread_id=thread_id, error="invalid or expired upload token"
                        ),
                    )
                    return

                logger.info(
                    "upload associated successfully",
                )

            config = self._build_config(
                thread_id=thread_id,
                metadata=request.metadata,
            )

            state = self._prepare_state(
                message=request.message,
                dataset_path=dataset_path,
            )

            yield MetadataGeneratedEvent(
                event=GenerationEventType.METADATA,
                data=EventMetadata(
                    thread_id=thread_id,
                ),
            )

            async for event in self.agent_graph.astream_events(
                state,
                config,
                version="v2",
            ):
                event_type = event.get("event")

                node = {"node": event.get("metadata", {}).get("langgraph_node")}

                if event_type == "on_chat_model_start":
                    logger.info(
                        f"LLM called: {node}",
                    )

                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content_text = self._extract_text_content(chunk.content)
                        if not content_text:
                            continue
                        yield TokenGeneratedEvent(
                            event=GenerationEventType.TOKEN_EVENT,
                            data=TokenEvent(
                                content=content_text,
                                thread_id=thread_id,
                            ),
                        )
                elif event_type == "on_tool_start":
                    tool_name = event.get("name")
                    tool_input = event.get("data", {}).get("input")

                    logger.info(
                        f"tool start: {tool_name}", extra={"input": str(tool_input)}
                    )

                    yield ToolStartGeneratedEvent(
                        event=GenerationEventType.TOOL_START_EVENT,
                        data=ToolStartEvent(
                            tool=tool_name,
                            thread_id=thread_id,
                        ),
                    )

                elif event_type == "on_tool_end":
                    tool_name = event.get("name")
                    tool_output = str(event.get("data", {}).get("output"))

                    logger.info(
                        f"tool end: {tool_name}",
                    )

                    yield ToolEndGeneratedEvent(
                        event=GenerationEventType.TOOL_END_EVENT,
                        data=ToolEndEvent(
                            tool=tool_name,
                            output=tool_output,
                            thread_id=thread_id,
                        ),
                    )

                logger.info("generation completed successfully")

                yield DoneGeneratedEvent(
                    event=GenerationEventType.DONE_EVENT,
                    data=DoneEvent(
                        thread_id=thread_id,
                        status="completed",
                    ),
                )

        except Exception as e:
            logger.exception(f"error in streaming: {str(e)}")
            yield ErrorGeneratedEvent(
                event=GenerationEventType.ERROR_EVENT,
                data=ErrorEvent(thread_id=thread_id, error=str(e)),
            )

    async def get_session_history(self, thread_id: str) -> List[HistoryMessages]:
        config = self._build_config(thread_id=thread_id)

        state_snapshot = await self.agent_graph.aget_state(config=config)

        if not state_snapshot.values:
            return []

        messages = state_snapshot.values.get("messages", [])

        formatted_messages = []

        for msg in messages:
            msg_type = msg.type
            content = self._extract_text_content(msg.content)
            tool_calls = getattr(msg, "tool_calls", [])
            tool_call_id = getattr(msg, "tool_call_id", None)

            formatted_messages.append(
                HistoryMessages(
                    type=msg_type,
                    content=content,
                    tool_calls=tool_calls,
                    tool_call_id=tool_call_id,
                )
            )

        return formatted_messages
