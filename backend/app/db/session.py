import asyncio
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base

_engine: Any = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
        )

        @event.listens_for(_engine.sync_engine, "connect")
        def _register_pgvector(dbapi_connection: object, _connection_record: object) -> None:
            try:
                from pgvector.asyncpg import register_vector
            except ImportError:
                return
            try:
                asyncio.run(register_vector(dbapi_connection))  # type: ignore[arg-type]
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(register_vector(dbapi_connection))  # type: ignore[arg-type]
                finally:
                    loop.close()

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


async def init_db_schema() -> None:
    """Optional: create tables for dev without Alembic (Phase 2 uses SQL migrations)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
