"""Assemble persisted observability payloads for QA Console (latency, status, cost placeholders)."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.services.observability.turn_metrics import CopilotTurnMetrics


def infer_turn_status(tool_trace: list[dict[str, Any]], weak_evidence: bool) -> str:
    for step in tool_trace:
        r = step.get("result")
        if isinstance(r, dict) and r.get("error"):
            return "error"
    if weak_evidence:
        return "warning"
    return "ok"


def build_observability_metadata(
    *,
    settings: Settings,
    metrics: CopilotTurnMetrics,
    agent_loop_ms: float,
    synthesis_ms: float,
    total_wall_ms: float,
    tool_trace: list[dict[str, Any]],
    weak_evidence: bool,
) -> dict[str, Any]:
    return {
        "status": infer_turn_status(tool_trace, weak_evidence),
        "langsmith": {
            "project": settings.langsmith_project if settings.langsmith_tracing else None,
            "tracing_enabled": settings.langsmith_tracing,
        },
        "latency_ms": {
            "agent_loop": round(agent_loop_ms, 2),
            "synthesis": round(synthesis_ms, 2),
            "retrieval_sum": round(metrics.retrieval_ms, 2),
            "tools_dispatch_sum": round(metrics.tools_dispatch_ms, 2),
            "tool_calls": metrics.tool_calls,
            "total_wall": round(total_wall_ms, 2),
        },
        "cost": {
            "estimated_usd": None,
            "note": "Placeholder — wire OpenAI usage tokens to cost when available.",
        },
    }
