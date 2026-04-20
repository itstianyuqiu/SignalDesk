"""HTTP schemas for case workflow APIs."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateCaseFromSessionBody(BaseModel):
    session_id: UUID = Field(description="Copilot session to materialize as a case.")


class CaseActionItemOut(BaseModel):
    id: UUID
    title: str
    status: Literal["todo", "in_progress", "done"]
    owner: str | None = None


class RelatedDocumentOut(BaseModel):
    id: UUID
    title: str
    tag: str = "Document"
    updated_at: datetime


class RelatedSessionOut(BaseModel):
    id: UUID
    title: str | None
    updated_at: datetime
    preview: str = ""


class TimelineEventOut(BaseModel):
    id: str
    kind: str
    label: str
    detail: str | None = None
    at: datetime
    actor: str | None = None


class CaseDetailOut(BaseModel):
    id: UUID
    caseKey: str
    title: str
    summary: str
    status: str
    priority: str
    category: str | None
    createdFromSessionId: UUID | None = None
    createdAt: datetime
    updatedAt: datetime
    actionItems: list[CaseActionItemOut] = Field(default_factory=list)
    relatedSessions: list[RelatedSessionOut] = Field(default_factory=list)
    relatedDocuments: list[RelatedDocumentOut] = Field(default_factory=list)
    timelineEvents: list[TimelineEventOut] = Field(default_factory=list)


class CaseListItemOut(BaseModel):
    id: UUID
    caseKey: str
    title: str
    status: str
    priority: str
    category: str | None = None
    updatedAt: datetime


class CaseBriefOut(BaseModel):
    """Lightweight payload for Copilot banner."""

    id: UUID
    caseKey: str
    title: str
    summary: str
    status: str
    priority: str
    category: str | None = None
    createdFromSessionId: UUID | None = None


class CopilotCaseContextOut(BaseModel):
    """Payload when opening Copilot from a case."""

    case: CaseBriefOut
    actionItems: list[CaseActionItemOut] = Field(default_factory=list)
    relatedDocuments: list[RelatedDocumentOut] = Field(default_factory=list)
