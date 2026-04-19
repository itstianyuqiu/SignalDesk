from __future__ import annotations

import json
from typing import Annotated, AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserId, DbSession
from app.db.session import get_session_factory
from app.core.config import Settings, get_settings
from app.models.chat import ChatMessage, ChatSession
from app.schemas.copilot import (
    CopilotChatRequest,
    CopilotChatResponse,
    CopilotMessageOut,
    CopilotSessionDetailOut,
    CopilotSessionOut,
    SessionInsightsOut,
    SourceChunk,
    SupportStructuredOut,
    ToolCallRecordOut,
    TranscribeResponse,
)
from app.services.copilot.orchestrator import CopilotTurnResult, run_copilot_turn, stream_copilot_turn
from app.services.copilot.session_insights import generate_and_persist_session_insights
from app.services.copilot.voice_transcription import transcribe_audio_bytes

router = APIRouter(prefix="/copilot", tags=["copilot"])

_WHISPER_MODEL = "whisper-1"
_MAX_VOICE_BYTES = 15 * 1024 * 1024


def _to_response(result: CopilotTurnResult) -> CopilotChatResponse:
    structured: SupportStructuredOut | None = None
    if result.structured:
        structured = SupportStructuredOut.model_validate(result.structured)
    tool_trace = [
        ToolCallRecordOut(
            name=s.get("name"),
            call_id=s.get("call_id"),
            arguments=s.get("arguments"),
            result=s.get("result") if isinstance(s.get("result"), dict) else None,
        )
        for s in result.tool_trace
    ]
    return CopilotChatResponse(
        session_id=result.session_id,
        user_message_id=result.user_message_id,
        assistant_message_id=result.assistant_message_id,
        answer=result.answer,
        sources=[
            SourceChunk(
                chunk_id=s.chunk_id,
                document_id=s.document_id,
                title=s.title,
                score=s.score,
                excerpt=s.excerpt,
            )
            for s in result.sources
        ],
        weak_evidence=result.weak_evidence,
        structured=structured,
        tool_trace=tool_trace,
    )


@router.post("/chat", response_model=CopilotChatResponse)
async def copilot_chat(
    body: CopilotChatRequest,
    session: DbSession,
    user_id: CurrentUserId,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CopilotChatResponse:
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured.")
    try:
        result = await run_copilot_turn(
            session,
            user_id=user_id,
            session_id=body.session_id,
            message=body.message,
            settings=settings,
            input_mode=body.input_mode,
            voice_metadata=body.voice,
        )
    except ValueError as exc:
        if str(exc) == "Session not found":
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _to_response(result)


@router.post("/chat/stream")
async def copilot_chat_stream(
    body: CopilotChatRequest,
    user_id: CurrentUserId,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """SSE stream; opens its own DB session so the connection outlives the HTTP handler return."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured.")

    async def event_iter() -> AsyncIterator[bytes]:
        factory = get_session_factory()
        try:
            async with factory() as db:
                async for item in stream_copilot_turn(
                    db,
                    user_id=user_id,
                    session_id=body.session_id,
                    message=body.message,
                    settings=settings,
                    input_mode=body.input_mode,
                    voice_metadata=body.voice,
                ):
                    yield f"data: {json.dumps(item, default=str)}\n\n".encode("utf-8")
        except ValueError as exc:
            err = {"event": "error", "detail": str(exc)}
            yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
        except RuntimeError as exc:
            err = {"event": "error", "detail": str(exc)}
            yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
        except Exception as exc:
            err = {"event": "error", "detail": f"{type(exc).__name__}: {exc}"}
            yield f"data: {json.dumps(err, default=str)}\n\n".encode("utf-8")

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/voice/transcribe", response_model=TranscribeResponse)
async def transcribe_voice_clip(
    _user_id: CurrentUserId,
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
    language: str | None = Form(
        default=None,
        description="Optional BCP-47 hint (e.g. zh-CN); forwarded to Whisper as ISO-639-1.",
    ),
) -> TranscribeResponse:
    """Upload a short audio clip; returns Whisper text (client records, stops, then uploads)."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured.")
    raw = await file.read()
    if len(raw) > _MAX_VOICE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio too large (max {_MAX_VOICE_BYTES // (1024 * 1024)} MB).",
        )
    try:
        text = await transcribe_audio_bytes(
            api_key=settings.openai_api_key,
            audio=raw,
            filename=file.filename or "audio.webm",
            model=_WHISPER_MODEL,
            language=language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TranscribeResponse(text=text, model=_WHISPER_MODEL)


@router.post("/sessions/{session_id}/insights", response_model=SessionInsightsOut)
async def create_session_insights(
    session_id: UUID,
    session: DbSession,
    user_id: CurrentUserId,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionInsightsOut:
    """Generate session summary, action items, and case tags; persisted on session metadata."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured.")
    try:
        insights = await generate_and_persist_session_insights(
            session,
            user_id=user_id,
            session_id=session_id,
            api_key=settings.openai_api_key,
            model=settings.copilot_model,
        )
    except ValueError as exc:
        if str(exc) == "Session not found":
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SessionInsightsOut.model_validate(insights)


@router.get("/sessions/{session_id}", response_model=CopilotSessionDetailOut)
async def get_copilot_session_detail(
    session_id: UUID,
    session: DbSession,
    user_id: CurrentUserId,
) -> CopilotSessionDetailOut:
    chat = await session.get(ChatSession, session_id)
    if chat is None or chat.user_id != user_id or chat.channel != "copilot":
        raise HTTPException(status_code=404, detail="Session not found")
    return CopilotSessionDetailOut(
        id=chat.id,
        title=chat.title,
        metadata=dict(chat.metadata_ or {}),
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


@router.get("/sessions", response_model=list[CopilotSessionOut])
async def list_copilot_sessions(
    session: DbSession,
    user_id: CurrentUserId,
) -> list[CopilotSessionOut]:
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id, ChatSession.channel == "copilot")
        .order_by(ChatSession.updated_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        CopilotSessionOut(
            id=r.id,
            title=r.title,
            updated_at=r.updated_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[CopilotMessageOut])
async def list_session_messages(
    session_id: UUID,
    session: DbSession,
    user_id: CurrentUserId,
) -> list[CopilotMessageOut]:
    chat = await session.get(ChatSession, session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.position.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        CopilotMessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            position=m.position,
            created_at=m.created_at,
            metadata=dict(m.metadata_ or {}),
        )
        for m in rows
    ]
