"""Per-request context passed into tool execution (no globals)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings


@dataclass(frozen=True)
class ToolContext:
    """Scoped data for tool handlers — keeps execution testable and explicit."""

    db: AsyncSession
    user_id: UUID
    settings: Settings
    min_evidence_score: float
