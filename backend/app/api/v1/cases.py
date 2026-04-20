"""Case workflow API."""

from uuid import UUID

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import CurrentUserId, DbSession
from app.core.config import Settings, get_settings
from app.schemas.cases_api import (
    CaseBriefOut,
    CaseDetailOut,
    CaseListItemOut,
    CopilotCaseContextOut,
    CreateCaseFromSessionBody,
)
from app.schemas.common import ListMeta
from app.services.cases.create_from_session import create_case_from_copilot_session
from app.services.cases.detail import case_to_detail_out, list_cases_for_user

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseListResponse(BaseModel):
    items: list[CaseListItemOut]
    meta: ListMeta


@router.get("", response_model=CaseListResponse)
async def list_cases(
    session: DbSession,
    user_id: CurrentUserId,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> CaseListResponse:
    items, total = await list_cases_for_user(session, user_id=user_id, skip=skip, limit=limit)
    return CaseListResponse(
        items=items,
        meta=ListMeta(total=total, skip=skip, limit=limit),
    )


@router.post("/from-session", response_model=CaseDetailOut)
async def create_case_from_session(
    body: CreateCaseFromSessionBody,
    session: DbSession,
    user_id: CurrentUserId,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CaseDetailOut:
    try:
        case_row, _created = await create_case_from_copilot_session(
            session,
            user_id=user_id,
            copilot_session_id=body.session_id,
            settings=settings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    out = await case_to_detail_out(session, case_id=case_row.id, user_id=user_id)
    if out is None:
        raise HTTPException(status_code=500, detail="Case created but could not be loaded")
    return out


@router.get("/{case_id}/copilot-context", response_model=CopilotCaseContextOut)
async def get_case_copilot_context(
    case_id: UUID,
    session: DbSession,
    user_id: CurrentUserId,
) -> CopilotCaseContextOut:
    detail = await case_to_detail_out(session, case_id=case_id, user_id=user_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return CopilotCaseContextOut(
        case=CaseBriefOut(
            id=detail.id,
            caseKey=detail.caseKey,
            title=detail.title,
            summary=detail.summary,
            status=detail.status,
            priority=detail.priority,
            category=detail.category,
            createdFromSessionId=detail.createdFromSessionId,
        ),
        actionItems=detail.actionItems,
        relatedDocuments=detail.relatedDocuments,
    )


@router.get("/{case_id}", response_model=CaseDetailOut)
async def get_case(
    case_id: UUID,
    session: DbSession,
    user_id: CurrentUserId,
) -> CaseDetailOut:
    out = await case_to_detail_out(session, case_id=case_id, user_id=user_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return out
