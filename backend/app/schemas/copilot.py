from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SourceChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    title: str
    score: float = Field(description="Retrieval similarity score (higher is better).")
    excerpt: str


class CopilotChatRequest(BaseModel):
    session_id: UUID | None = Field(
        default=None,
        description="Existing copilot session; omit to start a new session.",
    )
    message: str = Field(min_length=1, max_length=12000)
    input_mode: Literal["text", "voice"] = Field(
        default="text",
        description="When voice, user message metadata records STT and session transcript rollup.",
    )
    voice: dict[str, Any] | None = Field(
        default=None,
        description="Optional STT metadata (mime_type, duration_sec, engine, etc.).",
    )


class TranscribeResponse(BaseModel):
    text: str
    model: str = "whisper-1"


class SessionInsightsOut(BaseModel):
    summary: str
    action_items: list[str] = Field(default_factory=list)
    case_tags: list[str] = Field(default_factory=list)
    generated_at: str
    model: str | None = None


class CopilotSessionDetailOut(BaseModel):
    id: UUID
    title: str | None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class EscalationOut(BaseModel):
    level: str = "none"
    rationale: str = ""


class SupportStructuredOut(BaseModel):
    """Structured support intelligence (Phase 4)."""

    answer: str
    action_items: list[dict[str, Any]] = Field(default_factory=list)
    escalation: EscalationOut = Field(default_factory=EscalationOut)
    support_reply_draft: str | None = None


class ToolCallRecordOut(BaseModel):
    name: str | None = None
    call_id: str | None = None
    arguments: str | None = None
    result: dict[str, Any] | None = None


class CopilotChatResponse(BaseModel):
    session_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    answer: str
    sources: list[SourceChunk]
    weak_evidence: bool = Field(
        description="True when retrieval is empty or scores are below the configured threshold.",
    )
    structured: SupportStructuredOut | None = Field(
        default=None,
        description="Validated support summary (action items, escalation, draft reply).",
    )
    tool_trace: list[ToolCallRecordOut] = Field(default_factory=list)


class CopilotSessionOut(BaseModel):
    id: UUID
    title: str | None
    updated_at: datetime
    created_at: datetime


class CopilotMessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    position: int
    created_at: datetime
    metadata: dict = Field(default_factory=dict)
