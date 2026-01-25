import uuid
from typing import Any, AsyncGenerator, Callable, TypedDict

import socketio
import structlog
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants.globals import DEV_ORIGINS, PROD_ORIGINS
from app.database.schema import Role
from app.models.service import ChatRequest
from app.service.chat_service import ChatService
from app.token.token_manager import TokenManager

logger = structlog.get_logger(__name__)


class SocketSession(TypedDict):
    role: Role
    user_id: int


if settings.is_development:
    origins = DEV_ORIGINS
else:
    origins = PROD_ORIGINS

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=origins,
)

socket_app = socketio.ASGIApp(sio)


class SocketEvents:
    def __init__(
        self,
        agent_graph: CompiledStateGraph,
        db: Callable[[], AsyncGenerator[AsyncSession, None]],
        token_manager: TokenManager,
    ):
        self.chat_service = ChatService(
            agent_graph=agent_graph,
            db=db,
        )
        self.token_manager = token_manager
        self.register_events()

    def register_events(self):

        @sio.on("connect")
        async def connect(sid, environ, auth):
            logger.info(f"socket connection attempt successful: {sid}")

            if not auth or "token" not in auth:
                logger.warning(f"missing auth token for sid: {sid}")
                raise ConnectionRefusedError(
                    "authentication failed: authentication token missing"
                )

            token_str = auth["token"]

            if token_str.startswith("Bearer "):
                token_str = token_str.split(" ")[1]

            try:
                payload = self.token_manager.verify_token(token=token_str)

                if not payload:
                    raise ConnectionRefusedError(
                        "authentication failed: invalid payload",
                    )

                await sio.save_session(
                    sid,
                    SocketSession(
                        role=payload.role,
                        user_id=payload.user_id,
                    ),
                )

                logger.info(f"socket connected and authenticated: {sid}")

            except Exception as e:
                logger.exception(f"unexpected auth error for {sid}: {str(e)}")
                raise ConnectionRefusedError("authentication failed: internal error")

        @sio.on("disconnect")
        async def disconnect(sid):
            logger.info(f"socket disconnected: {sid}")

        @sio.on("join_thread")
        async def handle_join(sid, data):
            thread_id = data.get("thread_id")
            if thread_id:
                await sio.enter_room(sid, thread_id)

        @sio.on("chat_message")
        async def handle_chat_message(sid, data: Any):
            logger.info(f"received message from {sid}")

            session = await sio.get_session(sid)
            if not session:
                logger.warning(f"unauthenticated message attempt from {sid}")
                await sio.emit("error", {"detail": "unauthorized"}, to=sid)
                return

            try:
                request = ChatRequest(**data)

                thread_id = request.thread_id or str(uuid.uuid4())

                is_new_conversation = request.thread_id is None

                await sio.enter_room(sid, thread_id)
                await sio.emit(
                    "metadata",
                    {
                        "thread_id": thread_id,
                    },
                    room=thread_id,
                )

                async for response_chunk in self.chat_service.generate_response(
                    request=request,
                    thread_id=thread_id,
                    is_new_conversation=is_new_conversation,
                ):
                    event_name = response_chunk["event"]
                    event_payload = response_chunk["data"]

                    await sio.emit(
                        event_name,
                        event_payload,
                        room=thread_id,
                    )

            except Exception as e:
                logger.exception(f"socket error processing message: {e}")
                await sio.emit(
                    "error",
                    {
                        "detail": "invalid request or processing error",
                    },
                    to=sid,
                )
