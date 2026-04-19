"""Register pgvector codecs on asyncpg connections inside the running asyncio loop.

Avoid ``asyncio.run(register_vector(...))`` in sync ``engine.connect`` hooks — that breaks
SQLAlchemy async + FastAPI on Windows (greenlet / pool issues).
"""

from __future__ import annotations

import weakref

from sqlalchemy.ext.asyncio import AsyncSession

# asyncpg.Connection uses __slots__ — cannot stash a registration flag on the instance.
_registered: weakref.WeakKeyDictionary[object, bool] = weakref.WeakKeyDictionary()


async def ensure_pgvector_registered(session: AsyncSession) -> None:
    """Idempotent per asyncpg connection."""
    conn = await session.connection()
    raw = await conn.get_raw_connection()
    apg = getattr(raw, "_connection", raw)
    if _registered.get(apg):
        return
    from pgvector.asyncpg import register_vector

    await register_vector(apg)
    _registered[apg] = True
