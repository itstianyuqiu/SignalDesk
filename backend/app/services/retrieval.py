"""Vector retrieval over document chunks."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.document import Document, DocumentChunk, DocumentVersion
from app.services.embeddings import embed_texts


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: UUID
    content: str
    score: float
    distance: float
    document_id: UUID
    version_id: UUID
    title: str
    tags: list[str]
    source_type: str
    created_at: object


def _score_from_cosine_distance(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 - (distance / 2.0)))


async def retrieve_chunks(
    session: AsyncSession,
    *,
    owner_id: UUID,
    query: str,
    top_k: int,
    settings: Settings,
    document_ids: list[UUID] | None = None,
    tags: list[str] | None = None,
    source_types: list[str] | None = None,
) -> list[RetrievedChunk]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    if not query.strip():
        raise ValueError("Query must not be empty.")

    query_vectors = await embed_texts([query.strip()], settings=settings)
    query_vector = query_vectors[0]

    distance_expr = DocumentChunk.embedding.cosine_distance(query_vector)  # type: ignore[union-attr]

    stmt: Select[tuple[DocumentChunk, float, Document, DocumentVersion]] = (
        select(DocumentChunk, distance_expr, Document, DocumentVersion)
        .join(DocumentVersion, DocumentChunk.document_version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(
            and_(
                Document.owner_id == owner_id,
                DocumentChunk.embedding.isnot(None),
            )
        )
    )

    if document_ids:
        stmt = stmt.where(Document.id.in_(document_ids))
    if tags:
        stmt = stmt.where(Document.tags.contains(tags))
    if source_types:
        stmt = stmt.where(Document.source_type.in_(source_types))

    stmt = stmt.order_by(distance_expr).limit(top_k)

    rows = (await session.execute(stmt)).all()
    results: list[RetrievedChunk] = []
    for chunk, distance, document, version in rows:
        dist = float(distance)
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                content=chunk.content,
                score=_score_from_cosine_distance(dist),
                distance=dist,
                document_id=document.id,
                version_id=version.id,
                title=document.title,
                tags=list(document.tags or []),
                source_type=document.source_type,
                created_at=chunk.created_at,
            )
        )
    return results
