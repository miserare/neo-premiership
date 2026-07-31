from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# SQLite (used by the tests) rejects the server-oriented pool tuning below, so
# it is only applied to a real database.
_is_sqlite = settings.database_url.startswith("sqlite")

_engine_kwargs: dict = {"echo": settings.sql_echo}
if not _is_sqlite:
    _engine_kwargs.update(
        # pre_ping discards a connection killed by a database restart or an idle
        # timeout between requests, rather than handing the corpse to a request.
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        # Recycle below typical upstream idle timeouts so we close connections
        # before something else does it for us.
        pool_recycle=settings.db_pool_recycle_seconds,
        connect_args={
            "timeout": settings.db_connect_timeout_seconds,
            "server_settings": {"application_name": "pokemon-premiership"},
        },
    )

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
