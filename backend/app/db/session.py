from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base

_engine: Any = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _asyncpg_connect_args(database_url: str, statement_cache_size: int | None) -> dict[str, Any]:
    """
    PgBouncer transaction mode (including Supabase Supavisor :6543) cannot use asyncpg's
    prepared-statement cache; without statement_cache_size=0 inserts often fail mysteriously.
    """
    if statement_cache_size is not None:
        return {"statement_cache_size": statement_cache_size}
    u = database_url.lower()
    if "pgbouncer=true" in u or "pooler.supabase.com" in u:
        return {"statement_cache_size": 0}
    if "supabase.co" in u and ":6543" in u:
        return {"statement_cache_size": 0}
    return {}


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        connect_args = _asyncpg_connect_args(
            settings.database_url,
            settings.asyncpg_statement_cache_size,
        )
        engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if connect_args:
            engine_kwargs["connect_args"] = connect_args
        _engine = create_async_engine(settings.database_url, **engine_kwargs)

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
