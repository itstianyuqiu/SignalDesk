from datetime import datetime
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


class CopilotChatResponse(BaseModel):
    session_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    answer: str
    sources: list[SourceChunk]
    weak_evidence: bool = Field(
        description="True when retrieval is empty or scores are below the configured threshold.",
    )


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
