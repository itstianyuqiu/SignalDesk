"""Mutable per-turn counters collected during a single copilot request."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CopilotTurnMetrics:
    """Wall-clock segments (milliseconds) — overlapping where noted in QA UI."""

    retrieval_ms: float = 0.0
    tools_dispatch_ms: float = 0.0
    tool_calls: int = 0
