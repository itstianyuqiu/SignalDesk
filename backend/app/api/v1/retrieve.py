from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from openai import APIError

from app.api.deps import CurrentUserId, DbSession
from app.api.openai_errors import raise_http_from_openai
from app.core.config import Settings, get_settings
from app.schemas.retrieve import RetrievedChunkOut, RetrieveRequest, RetrieveResponse
from app.services.retrieval import retrieve_chunks

router = APIRouter(prefix="/retrieve", tags=["retrieve"])


@router.post("", response_model=RetrieveResponse)
async def retrieve(
    body: RetrieveRequest,
    session: DbSession,
    user_id: CurrentUserId,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RetrieveResponse:
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured on the API server.")
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured on the API server.")

    filters = body.filters
    try:
        rows = await retrieve_chunks(
            session,
            owner_id=user_id,
            query=body.query,
            top_k=body.top_k,
            settings=settings,
            document_ids=filters.document_ids if filters else None,
            tags=filters.tags if filters else None,
            source_types=filters.source_types if filters else None,
        )
    except APIError as exc:
        raise_http_from_openai(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    items = [
        RetrievedChunkOut(
            chunk_id=r.chunk_id,
            content=r.content,
            score=r.score,
            distance=r.distance,
            document_id=r.document_id,
            version_id=r.version_id,
            title=r.title,
            tags=r.tags,
            source_type=r.source_type,
            created_at=r.created_at,  # type: ignore[arg-type]
        )
        for r in rows
    ]
    return RetrieveResponse(items=items)
