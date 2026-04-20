"""Compile and run the support intelligence LangGraph (linear: prep → agent → retrieval → synthesize → quality)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from app.services.copilot.tools.context import ToolContext
from app.services.copilot.workflow.nodes import (
    extract_retrieval,
    prepare_context,
    quality_signals,
    synthesize,
    tool_agent,
)
from app.services.copilot.bootstrap_retrieval import bootstrap_search_documents_trace
from app.services.copilot.workflow.state import CopilotGraphContext, CopilotWorkflowState


@dataclass(frozen=True, slots=True)
class SupportIntelligenceWorkflowResult:
    interim_assistant_text: str
    tool_trace: list[dict[str, Any]]
    selected_tools: list[str]
    retrieved_context: list[dict[str, Any]]
    structured: dict[str, Any]
    final_answer: str
    weak_evidence: bool
    confidence_hint: str
    agent_loop_ms: float
    synthesis_ms: float
    agent_node_errors: list[str]


def workflow_result_from_state(out: CopilotWorkflowState) -> SupportIntelligenceWorkflowResult:
    return SupportIntelligenceWorkflowResult(
        interim_assistant_text=str(out.get("interim_assistant_text") or ""),
        tool_trace=list(out.get("tool_trace") or []),
        selected_tools=list(out.get("selected_tools") or []),
        retrieved_context=list(out.get("retrieved_context") or []),
        structured=dict(out.get("structured") or {}),
        final_answer=str(out.get("final_answer") or ""),
        weak_evidence=bool(out.get("weak_evidence")),
        confidence_hint=str(out.get("confidence_hint") or "ok"),
        agent_loop_ms=float(out.get("agent_loop_ms") or 0.0),
        synthesis_ms=float(out.get("synthesis_ms") or 0.0),
        agent_node_errors=list(out.get("agent_node_errors") or []),
    )


async def run_postprocess_pipeline(state: CopilotWorkflowState) -> CopilotWorkflowState:
    """Deterministic post-tool steps (same semantics as the compiled graph tail). Used by streaming."""
    u1 = extract_retrieval(state)
    s1: CopilotWorkflowState = {**state, **u1}
    u2 = await synthesize(s1)
    s2: CopilotWorkflowState = {**s1, **u2}
    u3 = quality_signals(s2)
    return {**s2, **u3}


_compiled: Any | None = None


def get_support_intelligence_graph() -> Any:
    """Lazily compile a singleton graph (thread-safe enough for typical FastAPI usage)."""
    global _compiled
    if _compiled is None:
        builder = StateGraph(CopilotWorkflowState, context_schema=CopilotGraphContext)
        builder.add_node("prepare_context", prepare_context)
        builder.add_node("tool_agent", tool_agent)
        builder.add_node("extract_retrieval", extract_retrieval)
        builder.add_node("synthesize", synthesize)
        builder.add_node("quality_signals", quality_signals)
        builder.add_edge(START, "prepare_context")
        builder.add_edge("prepare_context", "tool_agent")
        builder.add_edge("tool_agent", "extract_retrieval")
        builder.add_edge("extract_retrieval", "synthesize")
        builder.add_edge("synthesize", "quality_signals")
        builder.add_edge("quality_signals", END)
        _compiled = builder.compile()
    return _compiled


@traceable(name="copilot.support_intelligence_workflow", run_type="chain")
async def run_support_intelligence_workflow(
    *,
    user_question: str,
    history_lines: list[str],
    api_key: str,
    model: str,
    tool_ctx: ToolContext,
    case_context_block: str | None = None,
) -> SupportIntelligenceWorkflowResult:
    graph = get_support_intelligence_graph()
    initial: CopilotWorkflowState = {
        "user_question": user_question.strip(),
        "history_lines": history_lines,
        "api_key": api_key,
        "model": model,
    }
    if case_context_block and case_context_block.strip():
        initial["case_context_block"] = case_context_block.strip()
    bootstrap = await bootstrap_search_documents_trace(tool_ctx, user_question)
    out = await graph.ainvoke(
        initial,
        context=CopilotGraphContext(
            tool_ctx=tool_ctx,
            bootstrap_tool_trace=tuple(bootstrap),
        ),
    )
    return workflow_result_from_state(out)
