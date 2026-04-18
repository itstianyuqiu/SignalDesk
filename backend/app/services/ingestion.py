"""Document ingestion pipeline (sync today; same entrypoints can run in a worker later)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.document import Document, DocumentChunk, DocumentVersion
from app.services.chunking import chunk_text
from app.services.embeddings import embed_texts
from app.services.text_extract import UnsupportedContentTypeError, extract_text


@dataclass(frozen=True)
class IngestionResult:
    document_id: UUID
    version_id: UUID
    chunk_count: int
    content_type: str


async def ingest_bytes(
    session: AsyncSession,
    *,
    owner_id: UUID,
    filename: str,
    raw_bytes: bytes,
    content_type: str | None,
    title: str | None,
    tags: list[str],
    source_type: str,
    settings: Settings,
) -> IngestionResult:
    try:
        text, kind = extract_text(content=raw_bytes, filename=filename, content_type=content_type)
    except UnsupportedContentTypeError:
        raise
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    chunks = chunk_text(
        text,
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
    )
    if not chunks:
        raise ValueError("No text content produced after extraction.")

    embeddings = await embed_texts(chunks, settings=settings)
    if len(embeddings) != len(chunks):
        raise RuntimeError("Embedding batch size mismatch.")

    digest = sha256(text.encode("utf-8")).hexdigest()
    display_title = (title or "").strip() or filename

    doc = Document(
        owner_id=owner_id,
        title=display_title,
        status="published",
        tags=tags,
        source_type=source_type,
    )
    session.add(doc)
    await session.flush()

    version = DocumentVersion(
        document_id=doc.id,
        version=1,
        source_uri=filename,
        content_sha256=digest,
        created_by=owner_id,
        metadata_={"extracted_as": kind, "bytes": len(raw_bytes)},
    )
    session.add(version)
    await session.flush()

    doc.current_version_id = version.id
    doc.updated_at = datetime.now(timezone.utc)

    for idx, (chunk_text_value, vector) in enumerate(zip(chunks, embeddings, strict=True)):
        session.add(
            DocumentChunk(
                document_version_id=version.id,
                chunk_index=idx,
                content=chunk_text_value,
                token_count=max(1, len(chunk_text_value) // 4),
                metadata_={
                    "embedding_model": settings.embedding_model,
                    "extracted_as": kind,
                },
                embedding=vector,
            )
        )

    await session.commit()

    return IngestionResult(
        document_id=doc.id,
        version_id=version.id,
        chunk_count=len(chunks),
        content_type=kind,
    )
