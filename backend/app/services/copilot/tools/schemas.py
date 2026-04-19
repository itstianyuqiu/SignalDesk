"""Pydantic models for tool arguments, tool results, and copilot structured outputs."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# --- Tool arguments (validated before execution) ---


class SearchDocumentsArgs(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=8, ge=1, le=16)


class GetCaseSummaryArgs(BaseModel):
    case_id: UUID


class ExtractActionItemsArgs(BaseModel):
    source_text: str = Field(min_length=1, max_length=24000)
    max_items: int = Field(default=10, ge=1, le=25)


class DraftSupportReplyArgs(BaseModel):
    issue_summary: str = Field(min_length=1, max_length=8000)
    tone: Literal["professional", "empathetic", "brief"] = "professional"
    recipient_name: str | None = Field(default=None, max_length=200)


# --- Tool result payloads (serialized to JSON for the model) ---


class ToolError(BaseModel):
    ok: Literal[False] = False
    error: str
    detail: str | None = None


class SearchDocumentsHit(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    score: float
    excerpt: str


class SearchDocumentsResult(BaseModel):
    ok: Literal[True] = True
    query: str
    hits: list[SearchDocumentsHit]
    weak_evidence: bool


class CaseMessageSummary(BaseModel):
    role: str
    content: str
    created_at: str


class CaseSummaryResult(BaseModel):
    ok: Literal[True] = True
    case_id: str
    case_number: str
    title: str
    status: str
    created_at: str
    updated_at: str
    recent_messages: list[CaseMessageSummary]
    message_count: int


class ActionItemOut(BaseModel):
    title: str
    priority: Literal["low", "medium", "high"] = "medium"
    owner: str | None = None


class ExtractActionItemsResult(BaseModel):
    ok: Literal[True] = True
    items: list[ActionItemOut]
    notes: str | None = None


class DraftSupportReplyResult(BaseModel):
    ok: Literal[True] = True
    draft: str
    tone: str


# --- Final structured copilot output (JSON schema + validation) ---


class EscalationStructured(BaseModel):
    level: Literal["none", "tier1", "tier2", "engineering", "leadership"] = "none"
    rationale: str = Field(default="", max_length=4000)


class SupportIntelligenceStructured(BaseModel):
    """Emitted once per turn for UI + traceability (stored on assistant message metadata)."""

    answer: str = Field(description="User-facing reply (markdown or plain text).")
    action_items: list[ActionItemOut] = Field(default_factory=list)
    escalation: EscalationStructured = Field(default_factory=EscalationStructured)
    support_reply_draft: str | None = Field(
        default=None,
        description="Optional ready-to-send customer email or chat reply.",
    )

    @field_validator("support_reply_draft", mode="before")
    @classmethod
    def _empty_draft_to_none(cls, value: object) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s or None
