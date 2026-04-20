from fastapi import APIRouter, Query

from app.schemas.common import ListMeta
from app.schemas.sessions import SessionListResponse

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> SessionListResponse:
    """List chat / workflow sessions (placeholder — DB wiring in a later phase)."""
    return SessionListResponse(
        items=[],
        meta=ListMeta(total=0, skip=skip, limit=limit),
    )
