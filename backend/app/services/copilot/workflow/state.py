"""Workflow state and runtime context for the support intelligence LangGraph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from typing_extensions import NotRequired, Required, TypedDict

from app.services.copilot.tools.context import ToolContext


@dataclass(frozen=True, slots=True)
class CopilotGraphContext:
    """Run-scoped dependencies (not checkpointed) injected via LangGraph `context=`."""

    tool_ctx: ToolContext
    #: Prepended to model-produced tool_trace (deterministic KB search on user question).
    bootstrap_tool_trace: tuple[dict[str, Any], ...] = ()


class CopilotWorkflowState(TypedDict, total=False):
    """Explicit graph state: deterministic fields vs model/tool outputs."""

    # --- Inputs (required at start) ---
    user_question: Required[str]
    history_lines: Required[list[str]]
    api_key: Required[str]
    model: Required[str]
    case_context_block: NotRequired[str]

    # --- Deterministic prep ---
    instructions: str
    user_input: str

    # --- Dynamic tool agent (model decides tools; outputs are recorded) ---
    interim_assistant_text: str
    tool_trace: list[dict[str, Any]]
    selected_tools: list[str]
    agent_loop_ms: float
    agent_node_errors: list[str]

    # --- Deterministic extraction from traces ---
    retrieved_context: list[dict[str, Any]]

    # --- Structured synthesis (LLM, fixed schema) ---
    structured: dict[str, Any]
    final_answer: str
    synthesis_ms: float

    # --- Quality / confidence hints ---
    weak_evidence: bool
    confidence_hint: str
