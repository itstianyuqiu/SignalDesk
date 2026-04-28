import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from openai import APIError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import CurrentUserId, CurrentUserIdEnsured, DbSession
from app.api.openai_errors import raise_http_from_openai
from app.core.config import Settings, get_settings
from app.models.document import Document
from app.schemas.common import ListMeta
from app.schemas.documents import DocumentListResponse, DocumentSummary, IngestResponse
from app.services.ingestion import ingest_bytes
from app.services.text_extract import UnsupportedContentTypeError

router = APIRouter(prefix="/documents", tags=["documents"])
_log = logging.getLogger(__name__)


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    session: DbSession,
    user_id: CurrentUserId,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> DocumentListResponse:
    base = select(Document).where(Document.owner_id == user_id)
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(Document).where(Document.owner_id == user_id),
            )
        ).scalar_one()
    )
    rows = (
        (
            await session.execute(
                base.order_by(Document.updated_at.desc()).offset(skip).limit(limit),
            )
        )
        .scalars()
        .all()
    )
    items = [
        DocumentSummary(
            id=doc.id,
            owner_id=doc.owner_id,
            title=doc.title,
            status=doc.status,  # type: ignore[arg-type]
            tags=list(doc.tags or []),
            source_type=doc.source_type,
            current_version_id=doc.current_version_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc in rows
    ]
    return DocumentListResponse(items=items, meta=ListMeta(total=total, skip=skip, limit=limit))


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    session: DbSession,
    user_id: CurrentUserIdEnsured,
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    source_type: str = Form(default="upload"),
) -> IngestResponse:
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured on the API server.")
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured on the API server.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file.")

    filename = file.filename or "upload.bin"
    tag_list = _parse_tags(tags)

    try:
        result = await ingest_bytes(
            session,
            owner_id=user_id,
            filename=filename,
            raw_bytes=raw,
            content_type=file.content_type,
            title=title,
            tags=tag_list,
            source_type=source_type,
            settings=settings,
        )
    except APIError as exc:
        raise_http_from_openai(exc)
    except UnsupportedContentTypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        _log.exception("ingest failed during database commit")
        base = (
            "Database error while saving document chunks. "
            "Confirm `002_pgvector_rag.sql` is applied (vector extension + embedding column). "
            "If you use Supabase pooler port 6543, ensure asyncpg uses statement_cache_size=0 (set automatically for pooler URLs)."
        )
        if settings.environment == "local":
            base = f"{base} Postgres: {exc}"
        elif "row-level security" in str(exc).lower() or "rls" in str(exc).lower():
            base = (
                f"{base} RLS blocked this write: connect with a DB role that bypasses RLS for server-side jobs "
                "(see Supabase database password / direct connection), or adjust policies."
            )
        raise HTTPException(status_code=503, detail=base) from exc

    return IngestResponse(
        document_id=result.document_id,
        version_id=result.version_id,
        chunk_count=result.chunk_count,
        extracted_as=result.content_type,
    )
