"""Collect document IDs cited in Copilot message metadata (retrieval sources)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage


async def collect_document_ids_from_session(
    session: AsyncSession,
    session_id: UUID,
) -> list[UUID]:
    stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
    rows = (await session.execute(stmt)).scalars().all()
    found: set[UUID] = set()
    for m in rows:
        meta = m.metadata_ or {}
        for src in meta.get("sources") or []:
            if not isinstance(src, dict):
                continue
            raw = src.get("document_id")
            if not raw:
                continue
            try:
                found.add(UUID(str(raw)))
            except (ValueError, TypeError):
                continue
    return list(found)
