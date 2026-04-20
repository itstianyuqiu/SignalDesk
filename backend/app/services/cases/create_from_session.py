"""Create a support case from an existing Copilot session."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.case import Case, CaseActionItem, CaseDocument
from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document
from app.services.cases.document_refs import collect_document_ids_from_session
from app.services.copilot.session_insights import (
    generate_and_persist_session_insights,
    load_conversation_text,
)

logger = logging.getLogger(__name__)

_PLACEHOLDER_SUMMARY = (
    "Case created from this Copilot conversation. Generate a session summary to enrich this field."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_case_number() -> str:
    y = datetime.now(timezone.utc).year
    return f"CASE-{y}-{uuid.uuid4().hex[:6].upper()}"


def _category_from_tags(tags: list[str]) -> str | None:
    if not tags:
        return "General"
    raw = tags[0].strip()
    if not raw:
        return "General"
    return raw.replace("_", " ").replace("-", " ").title()


def _needs_session_insights(meta: dict[str, Any]) -> bool:
    ins = meta.get("session_insights")
    if not isinstance(ins, dict):
        return True
    s = str(ins.get("summary") or "").strip()
    if not s or s in (_PLACEHOLDER_SUMMARY, "No summary generated."):
        return True
    if s.startswith("Case created from this Copilot conversation"):
        return True
    return False


async def _fallback_summary_blurb(
    session: AsyncSession,
    session_id: UUID,
    *,
    max_chars: int = 1200,
) -> str:
    blob = await load_conversation_text(session, session_id, max_chars=8000)
    if not blob.strip():
        return _PLACEHOLDER_SUMMARY
    text = blob.strip().replace("\r\n", "\n")
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    return f"Conversation excerpt (auto):\n{text}"


async def _ensure_session_insights(
    session: AsyncSession,
    *,
    user_id: UUID,
    copilot_session_id: UUID,
    settings: Settings | None,
) -> None:
    """Populate session_insights via LLM when missing — same as POST /copilot/sessions/.../insights."""
    chat = await session.get(ChatSession, copilot_session_id)
    if chat is None:
        return
    meta = dict(chat.metadata_ or {})
    if not _needs_session_insights(meta):
        return
    if not settings or not settings.openai_api_key:
        return
    try:
        await generate_and_persist_session_insights(
            session,
            user_id=user_id,
            session_id=copilot_session_id,
            api_key=settings.openai_api_key,
            model=settings.copilot_model,
        )
    except ValueError as exc:
        logger.info("session_insights_skipped", extra={"reason": str(exc)})
    except Exception as exc:  # noqa: BLE001
        logger.warning("session_insights_failed", extra={"err": str(exc)})


async def create_case_from_copilot_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    copilot_session_id: UUID,
    settings: Settings | None = None,
) -> tuple[Case, bool]:
    """
    Returns (case, created) where created is False if the session already had a case.
    """
    chat = await session.get(ChatSession, copilot_session_id)
    if chat is None or chat.user_id != user_id:
        raise ValueError("Session not found")
    if chat.channel != "copilot":
        raise ValueError("Only Copilot sessions can create cases")

    if chat.case_id is not None:
        existing = await session.get(Case, chat.case_id)
        if existing is not None:
            return existing, False

    existing_by_origin = (
        await session.execute(select(Case).where(Case.created_from_session_id == copilot_session_id))
    ).scalar_one_or_none()
    if existing_by_origin is not None:
        chat.case_id = existing_by_origin.id
        await session.commit()
        await session.refresh(chat)
        return existing_by_origin, False

    await _ensure_session_insights(
        session,
        user_id=user_id,
        copilot_session_id=copilot_session_id,
        settings=settings,
    )
    chat = await session.get(ChatSession, copilot_session_id)
    if chat is None:
        raise ValueError("Session not found")

    meta = dict(chat.metadata_ or {})
    insights = meta.get("session_insights") if isinstance(meta.get("session_insights"), dict) else {}
    summary = str(insights.get("summary") or "").strip()
    if (
        not summary
        or summary.startswith("Case created from this Copilot conversation")
        or summary == "No summary generated."
    ):
        summary = await _fallback_summary_blurb(session, copilot_session_id)
    if not summary.strip():
        summary = _PLACEHOLDER_SUMMARY
    action_strings: list[str] = []
    raw_items = insights.get("action_items")
    if isinstance(raw_items, list):
        action_strings = [str(x).strip() for x in raw_items if str(x).strip()][:24]
    tags: list[str] = []
    raw_tags = insights.get("case_tags")
    if isinstance(raw_tags, list):
        tags = [str(x).strip() for x in raw_tags if str(x).strip()][:8]

    title = (chat.title or "").strip()
    if not title:
        first_user = (
            await session.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.session_id == copilot_session_id,
                    ChatMessage.role == "user",
                )
                .order_by(ChatMessage.position.asc())
                .limit(1),
            )
        ).scalar_one_or_none()
        if first_user and first_user.content.strip():
            title = first_user.content.strip().replace("\r\n", " ")[:120]
        else:
            title = "Case from Copilot"

    category = _category_from_tags(tags)

    doc_ids = await collect_document_ids_from_session(session, copilot_session_id)

    timeline: list[dict[str, Any]] = [
        {
            "id": str(uuid.uuid4()),
            "kind": "created",
            "label": "Case created from conversation",
            "detail": f"Source Copilot session {copilot_session_id}",
            "at": _now_iso(),
            "actor": "Support Intelligence",
        },
    ]
    if summary != _PLACEHOLDER_SUMMARY:
        timeline.append(
            {
                "id": str(uuid.uuid4()),
                "kind": "summary_updated",
                "label": "Case summary prepared from conversation",
                "detail": (
                    "Includes AI session insights when generated; otherwise a short transcript excerpt."
                ),
                "at": _now_iso(),
                "actor": "Support Intelligence",
            },
        )
    if action_strings:
        timeline.append(
            {
                "id": str(uuid.uuid4()),
                "kind": "actions_generated",
                "label": "Action items created",
                "detail": f"{len(action_strings)} item(s) from session insights",
                "at": _now_iso(),
                "actor": "Support Intelligence",
            },
        )

    case_row = Case(
        case_number=_generate_case_number(),
        title=title,
        summary=summary,
        status="open",
        priority="medium",
        category=category,
        opened_by=user_id,
        created_from_session_id=copilot_session_id,
        metadata_={"timeline": timeline},
    )
    session.add(case_row)
    await session.flush()

    for t in action_strings:
        session.add(
            CaseActionItem(
                case_id=case_row.id,
                title=t,
                status="todo",
                owner=None,
            ),
        )

    for did in doc_ids:
        doc = await session.get(Document, did)
        if doc is None or doc.owner_id != user_id:
            continue
        session.add(
            CaseDocument(
                case_id=case_row.id,
                document_id=did,
            ),
        )

    chat.case_id = case_row.id
    await session.commit()
    await session.refresh(case_row)
    return case_row, True
