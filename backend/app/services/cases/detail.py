"""Map DB rows to CaseDetailOut and list helpers."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case, CaseActionItem, CaseDocument
from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document
from app.schemas.cases_api import (
    CaseActionItemOut,
    CaseDetailOut,
    CaseListItemOut,
    RelatedDocumentOut,
    RelatedSessionOut,
    TimelineEventOut,
)
from app.services.cases.access import user_can_access_case


def _preview_from_messages(messages: list[ChatMessage], limit: int = 200) -> str:
    for m in reversed(messages):
        if m.role != "assistant":
            continue
        t = m.content.strip()
        if not t:
            continue
        t = t.replace("\r\n", "\n")
        return (t[:limit] + "…") if len(t) > limit else t
    return ""


async def case_to_detail_out(
    session: AsyncSession,
    *,
    case_id: UUID,
    user_id: UUID,
) -> CaseDetailOut | None:
    case_row = await session.get(Case, case_id)
    if case_row is None:
        return None
    if not await user_can_access_case(session, case=case_row, user_id=user_id):
        return None

    items = (
        (
            await session.execute(
                select(CaseActionItem)
                .where(CaseActionItem.case_id == case_id)
                .order_by(CaseActionItem.created_at.asc()),
            )
        )
        .scalars()
        .all()
    )
    action_out = [
        CaseActionItemOut(
            id=i.id,
            title=i.title,
            status=i.status,  # type: ignore[arg-type]
            owner=i.owner,
        )
        for i in items
    ]

    doc_rows = (
        (
            await session.execute(
                select(Document, CaseDocument.created_at)
                .join(CaseDocument, CaseDocument.document_id == Document.id)
                .where(CaseDocument.case_id == case_id),
            )
        )
        .all()
    )
    related_docs: list[RelatedDocumentOut] = []
    for doc, _cd_at in doc_rows:
        related_docs.append(
            RelatedDocumentOut(
                id=doc.id,
                title=doc.title,
                tag="Document",
                updated_at=doc.updated_at,
            ),
        )

    sessions_out: list[RelatedSessionOut] = []
    if case_row.created_from_session_id:
        src = await session.get(ChatSession, case_row.created_from_session_id)
        if src is not None and src.user_id == user_id:
            msgs = (
                (
                    await session.execute(
                        select(ChatMessage)
                        .where(ChatMessage.session_id == src.id)
                        .order_by(ChatMessage.position.asc()),
                    )
                )
                .scalars()
                .all()
            )
            sessions_out.append(
                RelatedSessionOut(
                    id=src.id,
                    title=src.title,
                    updated_at=src.updated_at,
                    preview=_preview_from_messages(list(msgs)),
                ),
            )

    meta = dict(case_row.metadata_ or {})
    raw_tl = meta.get("timeline")
    timeline: list[TimelineEventOut] = []
    if isinstance(raw_tl, list):
        for ev in raw_tl:
            if not isinstance(ev, dict):
                continue
            at_raw = ev.get("at")
            try:
                if isinstance(at_raw, datetime):
                    at_dt = at_raw
                else:
                    at_dt = datetime.fromisoformat(str(at_raw).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            timeline.append(
                TimelineEventOut(
                    id=str(ev.get("id") or ""),
                    kind=str(ev.get("kind") or "note"),
                    label=str(ev.get("label") or "Event"),
                    detail=str(ev.get("detail")) if ev.get("detail") else None,
                    at=at_dt,
                    actor=str(ev.get("actor")) if ev.get("actor") else None,
                ),
            )

    return CaseDetailOut(
        id=case_row.id,
        caseKey=case_row.case_number,
        title=case_row.title,
        summary=case_row.summary,
        status=case_row.status,
        priority=case_row.priority,
        category=case_row.category,
        createdFromSessionId=case_row.created_from_session_id,
        createdAt=case_row.created_at,
        updatedAt=case_row.updated_at,
        actionItems=action_out,
        relatedSessions=sessions_out,
        relatedDocuments=related_docs,
        timelineEvents=timeline,
    )


async def list_cases_for_user(
    session: AsyncSession,
    *,
    user_id: UUID,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[CaseListItemOut], int]:
    count_q = await session.execute(
        select(func.count())
        .select_from(Case)
        .where(or_(Case.opened_by == user_id, Case.assignee_id == user_id)),
    )
    total = int(count_q.scalar_one() or 0)

    stmt = (
        select(Case)
        .where(or_(Case.opened_by == user_id, Case.assignee_id == user_id))
        .order_by(Case.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    items = [
        CaseListItemOut(
            id=r.id,
            caseKey=r.case_number,
            title=r.title,
            status=r.status,
            priority=r.priority,
            category=r.category,
            updatedAt=r.updated_at,
        )
        for r in rows
    ]
    return items, total
