"""RAG copilot turn orchestration (retrieval + LLM + persistence)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.chat import ChatMessage, ChatSession
from app.services.copilot.openai_responses import generate_answer, stream_answer
from app.services.copilot.prompts import build_rag_prompt_bundle
from app.services.retrieval import RetrievedChunk, retrieve_chunks


@dataclass(frozen=True)
class SourceOut:
    chunk_id: UUID
    document_id: UUID
    title: str
    score: float
    excerpt: str


@dataclass(frozen=True)
class CopilotTurnResult:
    session_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    answer: str
    sources: list[SourceOut]
    weak_evidence: bool


def _chunks_to_sources(chunks: list[RetrievedChunk], *, excerpt_len: int = 320) -> list[SourceOut]:
    out: list[SourceOut] = []
    for ch in chunks:
        ex = ch.content.strip().replace("\r\n", "\n")
        if len(ex) > excerpt_len:
            ex = ex[:excerpt_len] + "…"
        out.append(
            SourceOut(
                chunk_id=ch.chunk_id,
                document_id=ch.document_id,
                title=ch.title,
                score=float(ch.score),
                excerpt=ex,
            )
        )
    return out


def _serialize_sources(sources: list[SourceOut]) -> list[dict]:
    return [
        {
            "chunk_id": str(s.chunk_id),
            "document_id": str(s.document_id),
            "title": s.title,
            "score": s.score,
            "excerpt": s.excerpt,
        }
        for s in sources
    ]


def _weak_evidence_flag(chunks: list[RetrievedChunk], *, min_score: float) -> bool:
    if not chunks:
        return True
    return max(ch.score for ch in chunks) < min_score


async def _next_message_position(session: AsyncSession, session_id: UUID) -> int:
    mx = (
        await session.execute(
            select(func.coalesce(func.max(ChatMessage.position), -1)).where(
                ChatMessage.session_id == session_id,
            ),
        )
    ).scalar_one()
    return int(mx) + 1


async def _load_prior_turns(
    session: AsyncSession,
    session_id: UUID,
    *,
    max_messages: int,
) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.position.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    if max_messages > 0 and len(rows) > max_messages:
        rows = rows[-max_messages:]
    return list(rows)


def _history_lines(msgs: list[ChatMessage]) -> list[str]:
    lines: list[str] = []
    for m in msgs:
        if m.role not in ("user", "assistant"):
            continue
        text = m.content.strip().replace("\r\n", "\n")
        if len(text) > 6000:
            text = text[:6000] + "…"
        lines.append(f"{m.role.upper()}: {text}")
    return lines


async def run_copilot_turn(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID | None,
    message: str,
    settings: Settings,
) -> CopilotTurnResult:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    text = message.strip()
    if not text:
        raise ValueError("Message must not be empty.")

    if session_id is None:
        title = text.replace("\r\n", " ")[:120] or "Copilot"
        chat = ChatSession(
            user_id=user_id,
            title=title,
            status="active",
            channel="copilot",
            metadata_={"kind": "copilot"},
        )
        session.add(chat)
        await session.flush()
        sid = chat.id
    else:
        chat = await session.get(ChatSession, session_id)
        if chat is None or chat.user_id != user_id:
            raise ValueError("Session not found")
        sid = chat.id

    pos = await _next_message_position(session, sid)
    user_row = ChatMessage(
        session_id=sid,
        role="user",
        content=text,
        position=pos,
        metadata_={},
    )
    session.add(user_row)
    await session.flush()

    prior = await _load_prior_turns(
        session,
        sid,
        max_messages=settings.copilot_max_history_messages,
    )
    # Include the just-inserted user message in prompt context
    history_msgs = [m for m in prior if m.id != user_row.id]
    history_msgs.append(user_row)
    history_lines = _history_lines(history_msgs)

    chunks = await retrieve_chunks(
        session,
        owner_id=user_id,
        query=text,
        top_k=settings.copilot_retrieval_top_k,
        settings=settings,
        document_ids=None,
        tags=None,
        source_types=None,
    )
    weak = _weak_evidence_flag(chunks, min_score=settings.copilot_min_evidence_score)
    bundle = build_rag_prompt_bundle(
        user_question=text,
        history_lines=history_lines,
        chunks=chunks,
        weak_evidence=weak,
    )

    answer = await generate_answer(
        api_key=settings.openai_api_key,
        model=settings.copilot_model,
        instructions=bundle.instructions,
        user_input=bundle.user_input,
    )
    if not answer:
        answer = (
            "I could not generate a response. Please try again or check API configuration."
        )

    sources = _chunks_to_sources(chunks)
    assistant_pos = pos + 1
    assistant_row = ChatMessage(
        session_id=sid,
        role="assistant",
        content=answer,
        position=assistant_pos,
        metadata_={
            "sources": _serialize_sources(sources),
            "weak_evidence": weak,
            "model": settings.copilot_model,
            "kind": "copilot_rag",
        },
    )
    session.add(assistant_row)

    chat = await session.get(ChatSession, sid)
    if chat is not None:
        chat.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(user_row)
    await session.refresh(assistant_row)

    return CopilotTurnResult(
        session_id=sid,
        user_message_id=user_row.id,
        assistant_message_id=assistant_row.id,
        answer=answer,
        sources=sources,
        weak_evidence=weak,
    )


async def stream_copilot_turn(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID | None,
    message: str,
    settings: Settings,
):
    """
    Async generator yielding text fragments, then a final dict with ids + sources metadata.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    text = message.strip()
    if not text:
        raise ValueError("Message must not be empty.")

    if session_id is None:
        title = text.replace("\r\n", " ")[:120] or "Copilot"
        chat = ChatSession(
            user_id=user_id,
            title=title,
            status="active",
            channel="copilot",
            metadata_={"kind": "copilot"},
        )
        session.add(chat)
        await session.flush()
        sid = chat.id
    else:
        chat = await session.get(ChatSession, session_id)
        if chat is None or chat.user_id != user_id:
            raise ValueError("Session not found")
        sid = chat.id

    pos = await _next_message_position(session, sid)
    user_row = ChatMessage(
        session_id=sid,
        role="user",
        content=text,
        position=pos,
        metadata_={},
    )
    session.add(user_row)
    await session.flush()

    prior = await _load_prior_turns(session, sid, max_messages=settings.copilot_max_history_messages)
    history_msgs = [m for m in prior if m.id != user_row.id]
    history_msgs.append(user_row)
    history_lines = _history_lines(history_msgs)

    chunks = await retrieve_chunks(
        session,
        owner_id=user_id,
        query=text,
        top_k=settings.copilot_retrieval_top_k,
        settings=settings,
    )
    weak = _weak_evidence_flag(chunks, min_score=settings.copilot_min_evidence_score)
    bundle = build_rag_prompt_bundle(
        user_question=text,
        history_lines=history_lines,
        chunks=chunks,
        weak_evidence=weak,
    )
    sources = _chunks_to_sources(chunks)

    yield {"event": "meta", "weak_evidence": weak, "sources": _serialize_sources(sources)}

    buf: list[str] = []
    async for delta in stream_answer(
        api_key=settings.openai_api_key,
        model=settings.copilot_model,
        instructions=bundle.instructions,
        user_input=bundle.user_input,
    ):
        if delta:
            buf.append(delta)
            yield {"event": "delta", "text": delta}

    answer = "".join(buf).strip() or (
        "I could not generate a streamed response. Please try again."
    )

    assistant_row = ChatMessage(
        session_id=sid,
        role="assistant",
        content=answer,
        position=pos + 1,
        metadata_={
            "sources": _serialize_sources(sources),
            "weak_evidence": weak,
            "model": settings.copilot_model,
            "kind": "copilot_rag_stream",
        },
    )
    session.add(assistant_row)
    chat2 = await session.get(ChatSession, sid)
    if chat2 is not None:
        chat2.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(user_row)
    await session.refresh(assistant_row)

    yield {
        "event": "done",
        "session_id": str(sid),
        "user_message_id": str(user_row.id),
        "assistant_message_id": str(assistant_row.id),
        "answer": answer,
    }
