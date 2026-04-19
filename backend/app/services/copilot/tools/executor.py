"""Dispatch tool calls to retrieval, DB reads, or bounded LLM helpers."""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from uuid import UUID

from langsmith import traceable
from pydantic import ValidationError

from app.models.case import Case
from app.models.chat import ChatMessage, ChatSession
from app.services.copilot.tools.context import ToolContext
from app.services.copilot.tools.llm_calls import llm_draft_support_reply, llm_extract_action_items
from app.services.copilot.tools.schemas import (
    CaseMessageSummary,
    CaseSummaryResult,
    DraftSupportReplyArgs,
    ExtractActionItemsArgs,
    GetCaseSummaryArgs,
    SearchDocumentsArgs,
    SearchDocumentsHit,
    SearchDocumentsResult,
    ToolError,
)
from app.services.retrieval import retrieve_chunks
from sqlalchemy import select

logger = logging.getLogger(__name__)

_EXCERPT_LEN = 320


def _excerpt(text: str) -> str:
    ex = text.strip().replace("\r\n", "\n")
    if len(ex) > _EXCERPT_LEN:
        return ex[:_EXCERPT_LEN] + "…"
    return ex


@traceable(name="copilot.tool.execute", run_type="tool")
async def execute_tool(
    name: str,
    raw_arguments: str,
    ctx: ToolContext,
) -> dict[str, Any]:
    """
    Run a named tool with JSON arguments from the model.
    Returns a JSON-serializable dict (success or ToolError).
    """
    t0 = time.perf_counter()
    try:
        data = json.loads(raw_arguments) if raw_arguments.strip() else {}
    except json.JSONDecodeError as exc:
        return ToolError(error="invalid_json_arguments", detail=str(exc)).model_dump()

    try:
        if name == "search_documents":
            out = await _search_documents(data, ctx)
        elif name == "get_case_summary":
            out = await _get_case_summary(data, ctx)
        elif name == "extract_action_items":
            out = await _extract_action_items(data, ctx)
        elif name == "draft_support_reply":
            out = await _draft_support_reply(data, ctx)
        else:
            out = ToolError(error="unknown_tool", detail=name).model_dump()
    except Exception as exc:  # noqa: BLE001 — surface as tool result, not HTTP 500
        logger.exception("tool_execution_failed", extra={"tool": name})
        out = ToolError(error="execution_failed", detail=f"{type(exc).__name__}: {exc}").model_dump()
    finally:
        if ctx.metrics is not None:
            elapsed = (time.perf_counter() - t0) * 1000.0
            ctx.metrics.tools_dispatch_ms += elapsed
            ctx.metrics.tool_calls += 1

    return out


async def _search_documents(data: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    try:
        args = SearchDocumentsArgs.model_validate(data)
    except ValidationError as exc:
        return ToolError(error="validation_error", detail=exc.errors().__str__()).model_dump()

    if not ctx.settings.openai_api_key:
        return ToolError(error="misconfigured", detail="Embeddings API unavailable.").model_dump()

    t_ret = time.perf_counter()
    try:
        chunks = await retrieve_chunks(
            ctx.db,
            owner_id=ctx.user_id,
            query=args.query,
            top_k=args.top_k,
            settings=ctx.settings,
        )
    except ValueError as exc:
        return ToolError(error="retrieval_error", detail=str(exc)).model_dump()
    finally:
        if ctx.metrics is not None:
            ctx.metrics.retrieval_ms += (time.perf_counter() - t_ret) * 1000.0

    weak = not chunks or max(ch.score for ch in chunks) < ctx.min_evidence_score
    hits = [
        SearchDocumentsHit(
            chunk_id=str(ch.chunk_id),
            document_id=str(ch.document_id),
            title=ch.title,
            score=float(ch.score),
            excerpt=_excerpt(ch.content),
        )
        for ch in chunks
    ]
    return SearchDocumentsResult(
        query=args.query,
        hits=hits,
        weak_evidence=weak,
    ).model_dump()


async def _get_case_summary(data: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    try:
        args = GetCaseSummaryArgs.model_validate(data)
    except ValidationError as exc:
        return ToolError(error="validation_error", detail=exc.errors().__str__()).model_dump()

    case_id = args.case_id
    case = await ctx.db.get(Case, case_id)
    if case is None:
        return ToolError(error="case_not_found", detail=str(case_id)).model_dump()

    uid = ctx.user_id
    if case.opened_by != uid and case.assignee_id != uid:
        return ToolError(
            error="forbidden",
            detail="Case is not visible to the current user (not opener or assignee).",
        ).model_dump()

    stmt = (
        select(ChatMessage)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.case_id == case_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(40)
    )
    rows = (await ctx.db.execute(stmt)).scalars().all()
    chronological = list(reversed(rows))
    recent = [
        CaseMessageSummary(
            role=m.role,
            content=m.content.strip().replace("\r\n", "\n")[:8000],
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in chronological
    ]

    return CaseSummaryResult(
        case_id=str(case.id),
        case_number=case.case_number,
        title=case.title,
        status=str(case.status),
        created_at=case.created_at.isoformat() if case.created_at else "",
        updated_at=case.updated_at.isoformat() if case.updated_at else "",
        recent_messages=recent,
        message_count=len(recent),
    ).model_dump()


async def _extract_action_items(data: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    try:
        args = ExtractActionItemsArgs.model_validate(data)
    except ValidationError as exc:
        return ToolError(error="validation_error", detail=exc.errors().__str__()).model_dump()

    if not ctx.settings.openai_api_key:
        return ToolError(error="misconfigured", detail="OPENAI_API_KEY missing.").model_dump()

    result = await llm_extract_action_items(
        api_key=ctx.settings.openai_api_key,
        model=ctx.settings.copilot_model,
        source_text=args.source_text,
        max_items=args.max_items,
    )
    return result.model_dump()


async def _draft_support_reply(data: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    try:
        args = DraftSupportReplyArgs.model_validate(data)
    except ValidationError as exc:
        return ToolError(error="validation_error", detail=exc.errors().__str__()).model_dump()

    if not ctx.settings.openai_api_key:
        return ToolError(error="misconfigured", detail="OPENAI_API_KEY missing.").model_dump()

    result = await llm_draft_support_reply(
        api_key=ctx.settings.openai_api_key,
        model=ctx.settings.copilot_model,
        args=args,
    )
    return result.model_dump()
