"""LangGraph node functions: deterministic steps vs dynamic tool-agent step."""

from __future__ import annotations

import logging
import time
from typing import Any

from langsmith import traceable
from langgraph.runtime import Runtime

from app.services.copilot.openai_responses import run_tool_agent_loop, synthesize_support_intelligence
from app.services.copilot.prompts import build_copilot_tool_agent_bundle
from app.services.copilot.tools.context import ToolContext
from app.services.copilot.trace_context import (
    confidence_hint,
    retrieved_context_records,
    weak_evidence_from_tool_trace,
)
from app.services.copilot.workflow.state import CopilotGraphContext, CopilotWorkflowState

logger = logging.getLogger(__name__)


@traceable(name="copilot.workflow.prepare_context", run_type="chain")
def prepare_context(state: CopilotWorkflowState) -> dict[str, Any]:
    """Deterministic: build instructions + user turn from history (no LLM)."""
    cc = state.get("case_context_block")
    bundle = build_copilot_tool_agent_bundle(
        user_question=state["user_question"],
        history_lines=state["history_lines"],
        case_context_block=cc if isinstance(cc, str) and cc.strip() else None,
    )
    return {"instructions": bundle.instructions, "user_input": bundle.user_input}


async def execute_tool_agent_phase(
    state: CopilotWorkflowState,
    tool_ctx: ToolContext,
) -> dict[str, Any]:
    """
    Dynamic: OpenAI tool-calling loop until the model stops requesting tools.
    Retries once on failure (transient API / network), then returns an empty trace for synthesis fallback.
    """
    ctx = tool_ctx
    t0 = time.perf_counter()
    errors: list[str] = []
    for attempt in range(2):
        try:
            agent = await run_tool_agent_loop(
                api_key=state["api_key"],
                model=state["model"],
                instructions=state["instructions"],
                user_input=state["user_input"],
                ctx=ctx,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            names = sorted({str(s.get("name") or "") for s in agent.tool_trace if s.get("name")})
            return {
                "interim_assistant_text": agent.interim_assistant_text,
                "tool_trace": agent.tool_trace,
                "selected_tools": names,
                "agent_loop_ms": elapsed_ms,
                "agent_node_errors": [],
            }
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            errors.append(err)
            logger.warning(
                "copilot_workflow_tool_agent_retry",
                extra={"attempt": attempt, "error": err},
            )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "interim_assistant_text": "",
        "tool_trace": [],
        "selected_tools": [],
        "agent_loop_ms": elapsed_ms,
        "agent_node_errors": errors,
    }


@traceable(name="copilot.workflow.tool_agent", run_type="chain")
async def tool_agent(
    state: CopilotWorkflowState,
    *,
    runtime: Runtime[CopilotGraphContext],
) -> dict[str, Any]:
    updates = await execute_tool_agent_phase(state, runtime.context.tool_ctx)
    trace = list(updates.get("tool_trace") or [])
    boot = runtime.context.bootstrap_tool_trace
    if boot:
        trace = list(boot) + trace
    return {**updates, "tool_trace": trace}


@traceable(name="copilot.workflow.extract_retrieval", run_type="chain")
def extract_retrieval(state: CopilotWorkflowState) -> dict[str, Any]:
    """Deterministic: normalize KB hits from `search_documents` tool results into explicit context."""
    trace = state.get("tool_trace") or []
    return {"retrieved_context": retrieved_context_records(trace)}


@traceable(name="copilot.workflow.synthesize", run_type="chain")
async def synthesize(state: CopilotWorkflowState) -> dict[str, Any]:
    """Structured synthesis pass (fixed JSON schema); internal parse fallback stays in openai_responses."""
    t0 = time.perf_counter()
    structured = await synthesize_support_intelligence(
        api_key=state["api_key"],
        model=state["model"],
        user_question=state["user_question"],
        interim_assistant_text=state.get("interim_assistant_text") or "",
        tool_trace=state.get("tool_trace") or [],
    )
    synthesis_ms = (time.perf_counter() - t0) * 1000.0
    answer = structured.answer.strip() or (
        "I could not generate a response. Please try again or check API configuration."
    )
    return {
        "structured": structured.model_dump(),
        "final_answer": answer,
        "synthesis_ms": synthesis_ms,
    }


@traceable(name="copilot.workflow.quality_signals", run_type="chain")
def quality_signals(state: CopilotWorkflowState) -> dict[str, Any]:
    """Deterministic quality hints for observability and UI."""
    trace = state.get("tool_trace") or []
    weak = weak_evidence_from_tool_trace(trace)
    return {
        "weak_evidence": weak,
        "confidence_hint": confidence_hint(weak_evidence=weak, tool_trace=trace),
    }
