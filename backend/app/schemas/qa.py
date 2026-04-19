"""QA Console API shapes — session list with counts and message detail (copilot channel)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class QASessionListItem(BaseModel):
    id: UUID
    title: str | None
    updated_at: datetime
    created_at: datetime
    message_count: int = Field(description="Total messages in the session.")


class QAMessageDetail(BaseModel):
    id: UUID
    role: str
    content: str
    position: int
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class QASessionDetail(BaseModel):
    session: QASessionListItem
    messages: list[QAMessageDetail]
