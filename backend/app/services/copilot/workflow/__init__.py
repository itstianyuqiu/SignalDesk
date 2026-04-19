"""LangGraph workflow for the support intelligence copilot (single linear graph)."""

from app.services.copilot.workflow.graph import (
    SupportIntelligenceWorkflowResult,
    run_support_intelligence_workflow,
)

__all__ = ("SupportIntelligenceWorkflowResult", "run_support_intelligence_workflow")
