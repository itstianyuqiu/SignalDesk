from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RetrieveFilters(BaseModel):
    document_ids: list[UUID] | None = Field(
        default=None,
        description="Restrict search to these documents (owned by caller).",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Documents must contain all of these tags (array superset).",
    )
    source_types: list[str] | None = Field(
        default=None,
        description="Match any of these source_type values.",
    )


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(default=8, ge=1, le=50)
    filters: RetrieveFilters | None = None


class RetrievedChunkOut(BaseModel):
    chunk_id: UUID
    content: str
    score: float = Field(description="Heuristic similarity score in [0,1] from cosine distance.")
    distance: float = Field(description="Raw pgvector cosine distance (lower is better).")
    document_id: UUID
    version_id: UUID
    title: str
    tags: list[str] = Field(default_factory=list)
    source_type: str
    created_at: datetime


class RetrieveResponse(BaseModel):
    items: list[RetrievedChunkOut]
