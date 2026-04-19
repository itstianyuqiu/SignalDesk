"""Configure LangSmith environment before traced code runs."""

from __future__ import annotations

import os

from app.core.config import Settings


def configure_langsmith(settings: Settings) -> None:
    """
    Sets LANGSMITH_* / legacy LANGCHAIN_TRACING_V2 for the process.
    Call once at application import/startup (see app.main).
    """
    key = (settings.langsmith_api_key or "").strip()
    if key:
        os.environ["LANGSMITH_API_KEY"] = key
    project = (settings.langsmith_project or "").strip()
    if project:
        os.environ["LANGSMITH_PROJECT"] = project

    if settings.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
