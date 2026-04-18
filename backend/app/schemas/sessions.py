from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ListMeta

CaseStatus = Literal["open", "pending", "resolved", "closed"]
SessionStatus = Literal["active", "closed"]


class CaseSummary(BaseModel):
    id: UUID
    case_number: str
    title: str
    status: CaseStatus
    opened_by: UUID | None = None
    assignee_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class SessionSummary(BaseModel):
    id: UUID
    case_id: UUID | None = None
    user_id: UUID
    title: str | None = None
    status: SessionStatus
    channel: str
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    items: list[SessionSummary] = Field(default_factory=list)
    meta: ListMeta


class SessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    case_id: UUID | None = None
    channel: str = Field(default="web", max_length=64)


class SessionCreateResponse(BaseModel):
    session: SessionSummary
    message: str = Field(
        default="Placeholder: persistence will connect to Postgres in a follow-up task.",
    )


class CaseListResponse(BaseModel):
    items: list[CaseSummary] = Field(default_factory=list)
    meta: ListMeta
