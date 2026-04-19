"""Session-level summary, action items, and case tags after a voice (or mixed) interaction."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession


async def load_conversation_text(
    session: AsyncSession,
    session_id: UUID,
    *,
    max_chars: int = 14000,
) -> str:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.position.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    parts: list[str] = []
    for m in rows:
        if m.role not in ("user", "assistant"):
            continue
        line = f"{m.role.upper()}: {m.content.strip()}"
        parts.append(line)
    blob = "\n".join(parts).strip()
    if len(blob) > max_chars:
        blob = blob[-max_chars:]
        blob = "…\n" + blob
    return blob


async def generate_and_persist_session_insights(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    chat = await session.get(ChatSession, session_id)
    if chat is None or chat.user_id != user_id:
        raise ValueError("Session not found")

    conversation = await load_conversation_text(session, session_id)
    if not conversation:
        raise ValueError("No messages to summarize.")

    client = AsyncOpenAI(api_key=api_key)
    schema_instruction = (
        'Return a JSON object with keys: "summary" (string, 2-5 sentences), '
        '"action_items" (array of short imperative strings; dedupe; empty if none), '
        '"case_tags" (array of 3-10 short lowercase snake_case or kebab labels describing '
        "topic, product area, sentiment, urgency; empty if unclear)."
    )
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You summarize internal support copilot conversations for agents. "
                    "Be factual; do not invent case facts not present in the transcript."
                ),
            },
            {
                "role": "user",
                "content": f"{schema_instruction}\n\nCONVERSATION:\n{conversation}",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Insights model returned invalid JSON.") from exc

    summary = str(parsed.get("summary") or "").strip()
    action_items = parsed.get("action_items")
    case_tags = parsed.get("case_tags")
    if not isinstance(action_items, list):
        action_items = []
    if not isinstance(case_tags, list):
        case_tags = []
    action_items = [str(x).strip() for x in action_items if str(x).strip()][:24]
    case_tags = [str(x).strip() for x in case_tags if str(x).strip()][:16]

    now = datetime.now(timezone.utc).isoformat()
    meta = dict(chat.metadata_ or {})
    insights = {
        "summary": summary or "No summary generated.",
        "action_items": action_items,
        "case_tags": case_tags,
        "model": model,
        "generated_at": now,
    }
    meta["session_insights"] = insights
    chat.metadata_ = meta
    await session.commit()
    await session.refresh(chat)
    return insights
