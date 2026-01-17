from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_async_engine(
    url=str(settings.DATABASE_URL),
    pool_pre_ping=True,
    connect_args={"options": "-c timezone=utc"},
)

db_session = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
)
