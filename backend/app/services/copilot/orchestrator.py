"""Copilot turn orchestration: tool calling, structured outputs, persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Any
from uuid import UUID

from langsmith import traceable
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.chat import ChatMessage, ChatSession
from app.services.copilot.tools.context import ToolContext
from app.services.copilot.trace_context import (
    SourceOut,
    aggregate_sources_from_tool_trace,
    weak_evidence_from_tool_trace,
)
from app.services.copilot.workflow.graph import (
    run_postprocess_pipeline,
    run_support_intelligence_workflow,
    workflow_result_from_state,
)
from app.services.copilot.workflow.nodes import execute_tool_agent_phase, prepare_context
from app.services.copilot.workflow.state import CopilotWorkflowState
from app.services.observability.turn_metrics import CopilotTurnMetrics
from app.services.observability.turn_observability import build_observability_metadata


@dataclass(frozen=True)
class CopilotTurnResult:
    session_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    answer: str
    sources: list[SourceOut]
    weak_evidence: bool
    structured: dict[str, Any]
    tool_trace: list[dict[str, Any]]


def _serialize_sources(sources: list[SourceOut]) -> list[dict]:
    return [
        {
            "chunk_id": str(s.chunk_id),
            "document_id": str(s.document_id),
            "title": s.title,
            "score": s.score,
            "excerpt": s.excerpt,
        }
        for s in sources
    ]


async def _next_message_position(session: AsyncSession, session_id: UUID) -> int:
    mx = (
        await session.execute(
            select(func.coalesce(func.max(ChatMessage.position), -1)).where(
                ChatMessage.session_id == session_id,
            ),
        )
    ).scalar_one()
    return int(mx) + 1


async def _load_prior_turns(
    session: AsyncSession,
    session_id: UUID,
    *,
    max_messages: int,
) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.position.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    if max_messages > 0 and len(rows) > max_messages:
        rows = rows[-max_messages:]
    return list(rows)


def _history_lines(msgs: list[ChatMessage]) -> list[str]:
    lines: list[str] = []
    for m in msgs:
        if m.role not in ("user", "assistant"):
            continue
        text = m.content.strip().replace("\r\n", "\n")
        if len(text) > 6000:
            text = text[:6000] + "…"
        lines.append(f"{m.role.upper()}: {text}")
    return lines


@traceable(name="copilot.turn", run_type="chain")
async def run_copilot_turn(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID | None,
    message: str,
    settings: Settings,
) -> CopilotTurnResult:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    text = message.strip()
    if not text:
        raise ValueError("Message must not be empty.")

    turn_t0 = time.perf_counter()

    if session_id is None:
        title = text.replace("\r\n", " ")[:120] or "Copilot"
        chat = ChatSession(
            user_id=user_id,
            title=title,
            status="active",
            channel="copilot",
            metadata_={"kind": "copilot"},
        )
        session.add(chat)
        await session.flush()
        sid = chat.id
    else:
        chat = await session.get(ChatSession, session_id)
        if chat is None or chat.user_id != user_id:
            raise ValueError("Session not found")
        sid = chat.id

    pos = await _next_message_position(session, sid)
    user_row = ChatMessage(
        session_id=sid,
        role="user",
        content=text,
        position=pos,
        metadata_={},
    )
    session.add(user_row)
    await session.flush()

    prior = await _load_prior_turns(
        session,
        sid,
        max_messages=settings.copilot_max_history_messages,
    )
    history_msgs = [m for m in prior if m.id != user_row.id]
    history_msgs.append(user_row)
    history_lines = _history_lines(history_msgs)

    metrics = CopilotTurnMetrics()
    tool_ctx = ToolContext(
        db=session,
        user_id=user_id,
        settings=settings,
        min_evidence_score=settings.copilot_min_evidence_score,
        metrics=metrics,
    )

    wf = await run_support_intelligence_workflow(
        user_question=text,
        history_lines=history_lines,
        api_key=settings.openai_api_key,
        model=settings.copilot_model,
        tool_ctx=tool_ctx,
    )
    agent_loop_ms = wf.agent_loop_ms
    synthesis_ms = wf.synthesis_ms

    answer = wf.final_answer.strip() or (
        "I could not generate a response. Please try again or check API configuration."
    )
    sources = aggregate_sources_from_tool_trace(wf.tool_trace)
    weak = wf.weak_evidence
    structured_dict = wf.structured
    total_wall_ms = (time.perf_counter() - turn_t0) * 1000.0
    observability = build_observability_metadata(
        settings=settings,
        metrics=metrics,
        agent_loop_ms=agent_loop_ms,
        synthesis_ms=synthesis_ms,
        total_wall_ms=total_wall_ms,
        tool_trace=wf.tool_trace,
        weak_evidence=weak,
    )

    assistant_pos = pos + 1
    assistant_row = ChatMessage(
        session_id=sid,
        role="assistant",
        content=answer,
        position=assistant_pos,
        metadata_={
            "sources": _serialize_sources(sources),
            "weak_evidence": weak,
            "model": settings.copilot_model,
            "kind": "copilot_tools",
            "structured": structured_dict,
            "tools": wf.tool_trace,
            "interim_assistant_text": wf.interim_assistant_text,
            "workflow": {
                "selected_tools": wf.selected_tools,
                "confidence_hint": wf.confidence_hint,
                "retrieved_context": wf.retrieved_context,
                "agent_node_errors": wf.agent_node_errors,
            },
            "observability": observability,
        },
    )
    session.add(assistant_row)

    chat = await session.get(ChatSession, sid)
    if chat is not None:
        chat.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(user_row)
    await session.refresh(assistant_row)

    return CopilotTurnResult(
        session_id=sid,
        user_message_id=user_row.id,
        assistant_message_id=assistant_row.id,
        answer=answer,
        sources=sources,
        weak_evidence=weak,
        structured=structured_dict,
        tool_trace=wf.tool_trace,
    )


async def stream_copilot_turn(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID | None,
    message: str,
    settings: Settings,
):
    """
    Async generator: tool events, meta (sources), text deltas, then done with ids.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    text = message.strip()
    if not text:
        raise ValueError("Message must not be empty.")

    turn_t0 = time.perf_counter()

    if session_id is None:
        title = text.replace("\r\n", " ")[:120] or "Copilot"
        chat = ChatSession(
            user_id=user_id,
            title=title,
            status="active",
            channel="copilot",
            metadata_={"kind": "copilot"},
        )
        session.add(chat)
        await session.flush()
        sid = chat.id
    else:
        chat = await session.get(ChatSession, session_id)
        if chat is None or chat.user_id != user_id:
            raise ValueError("Session not found")
        sid = chat.id

    pos = await _next_message_position(session, sid)
    user_row = ChatMessage(
        session_id=sid,
        role="user",
        content=text,
        position=pos,
        metadata_={},
    )
    session.add(user_row)
    await session.flush()

    prior = await _load_prior_turns(session, sid, max_messages=settings.copilot_max_history_messages)
    history_msgs = [m for m in prior if m.id != user_row.id]
    history_msgs.append(user_row)
    history_lines = _history_lines(history_msgs)

    metrics = CopilotTurnMetrics()
    tool_ctx = ToolContext(
        db=session,
        user_id=user_id,
        settings=settings,
        min_evidence_score=settings.copilot_min_evidence_score,
        metrics=metrics,
    )

    # Same graph semantics as `run_support_intelligence_workflow`, but yield tool events before synthesis.
    base: CopilotWorkflowState = {
        "user_question": text,
        "history_lines": history_lines,
        "api_key": settings.openai_api_key,
        "model": settings.copilot_model,
    }
    after_prep: CopilotWorkflowState = {**base, **prepare_context(base)}
    tool_updates = await execute_tool_agent_phase(after_prep, tool_ctx)
    agent_loop_ms = float(tool_updates.get("agent_loop_ms") or 0.0)
    after_agent: CopilotWorkflowState = {**after_prep, **tool_updates}

    for step in after_agent.get("tool_trace") or []:
        yield {
            "event": "tool",
            "name": step.get("name"),
            "call_id": step.get("call_id"),
            "arguments": step.get("arguments"),
            "result": step.get("result"),
        }

    final_state = await run_postprocess_pipeline(after_agent)
    wf = workflow_result_from_state(final_state)
    synthesis_ms = wf.synthesis_ms

    answer = wf.final_answer.strip() or (
        "I could not generate a streamed response. Please try again."
    )
    sources = aggregate_sources_from_tool_trace(wf.tool_trace)
    weak = wf.weak_evidence
    structured_dict = wf.structured
    total_wall_ms = (time.perf_counter() - turn_t0) * 1000.0
    observability = build_observability_metadata(
        settings=settings,
        metrics=metrics,
        agent_loop_ms=agent_loop_ms,
        synthesis_ms=synthesis_ms,
        total_wall_ms=total_wall_ms,
        tool_trace=wf.tool_trace,
        weak_evidence=weak,
    )

    yield {
        "event": "meta",
        "weak_evidence": weak,
        "sources": _serialize_sources(sources),
        "structured": structured_dict,
    }

    yield {"event": "delta", "text": answer}

    assistant_row = ChatMessage(
        session_id=sid,
        role="assistant",
        content=answer,
        position=pos + 1,
        metadata_={
            "sources": _serialize_sources(sources),
            "weak_evidence": weak,
            "model": settings.copilot_model,
            "kind": "copilot_tools_stream",
            "structured": structured_dict,
            "tools": wf.tool_trace,
            "interim_assistant_text": wf.interim_assistant_text,
            "workflow": {
                "selected_tools": wf.selected_tools,
                "confidence_hint": wf.confidence_hint,
                "retrieved_context": wf.retrieved_context,
                "agent_node_errors": wf.agent_node_errors,
            },
            "observability": observability,
        },
    )
    session.add(assistant_row)
    chat2 = await session.get(ChatSession, sid)
    if chat2 is not None:
        chat2.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(user_row)
    await session.refresh(assistant_row)

    yield {
        "event": "done",
        "session_id": str(sid),
        "user_message_id": str(user_row.id),
        "assistant_message_id": str(assistant_row.id),
        "answer": answer,
        "structured": structured_dict,
        "tool_trace": wf.tool_trace,
    }
