import structlog
import socketio
from langgraph.graph.state import CompiledStateGraph
from app.config import settings
from app.constants.globals import DEV_ORIGINS, PROD_ORIGINS
from app.service.chat_service import ChatService

logger = structlog.get_logger(__name__)

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
    def __init__(self, agent_graph: CompiledStateGraph):
        self.chat_service = ChatService(agent_graph=agent_graph)

    def register_events(self):

        @sio.on("connect")
        async def connect(sid, environ):
            logger.info(f"socket connection attempt successful: {sid}")

        @sio.on("disconnect")
        async def disconnect(sid):
            logger.info(f"socket disconnected: {sid}")

        @sio.on("join_thread")
        async def handle_join(sid, data):
            thread_id = data.get("thread_id")
            if thread_id:
                await sio.enter_room(sid, thread_id)

        