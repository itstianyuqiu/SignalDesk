"""Small OpenAI structured-output helpers used by tool execution (not the main agent loop)."""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from app.services.copilot.tools.schemas import (
    ActionItemOut,
    DraftSupportReplyArgs,
    DraftSupportReplyResult,
    ExtractActionItemsResult,
)


def _extract_output_text(response: object) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    out = getattr(response, "output", None) or []
    parts: list[str] = []
    for item in out:
        content = getattr(item, "content", None) or []
        for block in content:
            t = getattr(block, "text", None)
            if isinstance(t, str):
                parts.append(t)
    return "\n".join(parts).strip()


_ACTION_ITEMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "owner": {"type": "string"},
                },
                "required": ["title", "priority"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["items"],
    "additionalProperties": False,
}


async def llm_extract_action_items(
    *,
    api_key: str,
    model: str,
    source_text: str,
    max_items: int,
) -> ExtractActionItemsResult:
    client = AsyncOpenAI(api_key=api_key)
    clipped = source_text.strip()
    if len(clipped) > 12000:
        clipped = clipped[:12000] + "\n…"

    response = await client.responses.create(
        model=model,
        instructions=(
            f"Extract up to {max_items} distinct, actionable follow-ups from the text. "
            "Prefer imperative titles. If nothing actionable exists, return an empty items array."
        ),
        input=f"SOURCE_TEXT:\n{clipped}",
        text={
            "format": {
                "type": "json_schema",
                "name": "action_items",
                "strict": True,
                "schema": _ACTION_ITEMS_SCHEMA,
            }
        },
    )
    raw = _extract_output_text(response)
    data = json.loads(raw)
    items_raw = data.get("items") or []
    out_items: list[ActionItemOut] = []
    for it in items_raw[:max_items]:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title", "")).strip()
        if not title:
            continue
        pr = it.get("priority") or "medium"
        if pr not in ("low", "medium", "high"):
            pr = "medium"
        owner = it.get("owner")
        out_items.append(
            ActionItemOut(
                title=title,
                priority=pr,  # type: ignore[arg-type]
                owner=str(owner).strip() if owner else None,
            ),
        )
    notes = data.get("notes")
    return ExtractActionItemsResult(
        items=out_items,
        notes=str(notes).strip() if notes else None,
    )


_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "draft": {"type": "string"},
    },
    "required": ["draft"],
    "additionalProperties": False,
}


async def llm_draft_support_reply(
    *,
    api_key: str,
    model: str,
    args: DraftSupportReplyArgs,
) -> DraftSupportReplyResult:
    client = AsyncOpenAI(api_key=api_key)
    name_line = f"Recipient: {args.recipient_name}\n" if args.recipient_name else ""
    response = await client.responses.create(
        model=model,
        instructions=(
            "Write a concise support reply for email or chat. "
            f"Tone: {args.tone}. Do not invent policy; if facts are missing, acknowledge limits."
        ),
        input=f"{name_line}ISSUE:\n{args.issue_summary.strip()}",
        text={
            "format": {
                "type": "json_schema",
                "name": "support_draft",
                "strict": True,
                "schema": _DRAFT_SCHEMA,
            }
        },
    )
    raw = _extract_output_text(response)
    data = json.loads(raw)
    draft = str(data.get("draft", "")).strip() or "(empty draft)"
    return DraftSupportReplyResult(draft=draft, tone=args.tone)
