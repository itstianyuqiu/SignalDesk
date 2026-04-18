from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ListMeta

DocumentStatus = Literal["draft", "published", "archived"]


class DocumentSummary(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    status: DocumentStatus
    tags: list[str] = Field(default_factory=list)
    source_type: str = "upload"
    current_version_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary] = Field(default_factory=list)
    meta: ListMeta


class IngestResponse(BaseModel):
    document_id: UUID
    version_id: UUID
    chunk_count: int
    extracted_as: str = Field(description="text/plain or application/pdf")


class DocumentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    status: DocumentStatus = "draft"


class DocumentCreateResponse(BaseModel):
    document: DocumentSummary
    message: str = Field(
        default="Placeholder: persistence will connect to Postgres in a follow-up task.",
    )
