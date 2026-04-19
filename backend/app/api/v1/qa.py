"""QA Console: browse copilot sessions, transcripts, sources, tools, and observability metadata."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.api.deps import CurrentUserId, DbSession
from app.models.chat import ChatMessage, ChatSession
from app.schemas.qa import QAMessageDetail, QASessionDetail, QASessionListItem

router = APIRouter(prefix="/qa", tags=["qa"])


@router.get("/copilot-sessions", response_model=list[QASessionListItem])
async def list_qa_copilot_sessions(
    session: DbSession,
    user_id: CurrentUserId,
) -> list[QASessionListItem]:
    stmt = (
        select(ChatSession, func.count(ChatMessage.id))
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user_id, ChatSession.channel == "copilot")
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [
        QASessionListItem(
            id=chat.id,
            title=chat.title,
            updated_at=chat.updated_at,
            created_at=chat.created_at,
            message_count=int(cnt or 0),
        )
        for chat, cnt in rows
    ]


@router.get("/copilot-sessions/{session_id}", response_model=QASessionDetail)
async def get_qa_copilot_session_detail(
    session_id: UUID,
    session: DbSession,
    user_id: CurrentUserId,
) -> QASessionDetail:
    chat = await session.get(ChatSession, session_id)
    if chat is None or chat.user_id != user_id or chat.channel != "copilot":
        raise HTTPException(status_code=404, detail="Session not found")

    cnt = (
        await session.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id),
        )
    ).scalar_one()
    message_count = int(cnt or 0)

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.position.asc())
    )
    msgs = (await session.execute(stmt)).scalars().all()

    return QASessionDetail(
        session=QASessionListItem(
            id=chat.id,
            title=chat.title,
            updated_at=chat.updated_at,
            created_at=chat.created_at,
            message_count=message_count,
        ),
        messages=[
            QAMessageDetail(
                id=m.id,
                role=m.role,
                content=m.content,
                position=m.position,
                created_at=m.created_at,
                metadata=dict(m.metadata_ or {}),
            )
            for m in msgs
        ],
    )
