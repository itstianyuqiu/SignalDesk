"""Deterministic first-pass retrieval so Copilot always sees KB hits when they exist."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.copilot.tools.context import ToolContext
from app.services.copilot.tools.executor import execute_tool

logger = logging.getLogger(__name__)


async def bootstrap_search_documents_trace(
    tool_ctx: ToolContext,
    user_question: str,
) -> list[dict[str, Any]]:
    """
    Run the same `search_documents` path as the tool agent using the user's latest message.
    Prepended to tool_trace so synthesis and sources see chunks even if the model skips tools.
    """
    q = user_question.strip()
    if not q:
        return []
    raw = json.dumps(
        {
            "query": q,
            "top_k": tool_ctx.settings.copilot_retrieval_top_k,
        },
    )
    try:
        result = await execute_tool("search_documents", raw, tool_ctx)
    except Exception as exc:  # noqa: BLE001
        logger.warning("bootstrap_retrieval_failed", extra={"err": str(exc)})
        return []
    if not isinstance(result, dict) or result.get("ok") is False:
        return []
    return [
        {
            "name": "search_documents",
            "call_id": "bootstrap-retrieval",
            "arguments": raw,
            "result": result,
        },
    ]
