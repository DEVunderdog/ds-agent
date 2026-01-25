import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.token.token_manager import TokenManager
from app.constants.globals import DEV_ORIGINS, PROD_ORIGINS
from app.config import settings
from app.core.orchestrator.builder import GraphBuilder
from app.websocket.manager import SocketEvents, socket_app
from app.database.connection import get_db
from app.log.util import get_log_level, get_log_path
from app.log.manager import setup_logging
from app.exceptions.custom_exception_handler import request_validation_handler
from app.api.main import api_router

log_level = get_log_level()
log_path = get_log_path()

logger = setup_logging(
    log_dir=log_path,
    log_level=log_level,
    app_name=settings.PROJECT_NAME,
)

if settings.is_development:
    origin = DEV_ORIGINS
else:
    origin = PROD_ORIGINS


@asynccontextmanager
async def lifespan(app: FastAPI):

    if logger.handlers:
        file_handler = logger.handlers[0]

        access_logger = structlog.getLogger("uvicorn.access")
        access_logger.addHandler(file_handler)

        uvicorn_logger = structlog.getLogger("uvicorn")
        uvicorn_logger.addHandler(file_handler)

    app.state.token_manager = await TokenManager.create()

    async with AsyncPostgresSaver.from_conn_string(
        settings.CHECKPOINTER_DATABASE_URL
    ) as saver:
        await saver.setup()

        builder = GraphBuilder()

        app.state.agent_graph = await builder.build(checkpointer=saver)

        logger.info("graph compiled successfully")

        SocketEvents(
            agent_graph=app.state.agent_graph,
            token_manager=app.state.token_manager,
            db=get_db,
        )

        logger.info("Socket.IO events registered")

        yield

        logger.info("application server is shutting down")

    logger.info("cleanup complete, bye :)")


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origin,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RequestValidationError, request_validation_handler)

app.include_router(api_router)

app.mount("/", socket_app)
