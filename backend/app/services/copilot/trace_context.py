"""Derive retrieval / evidence signals from copilot tool traces (orchestrator + LangGraph workflow)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class SourceOut:
    chunk_id: UUID
    document_id: UUID
    title: str
    score: float
    excerpt: str


def aggregate_sources_from_tool_trace(tool_trace: list[dict[str, Any]]) -> list[SourceOut]:
    """Merge `search_documents` hits (retrieval layer — surfaced via tool results only)."""
    best: dict[UUID, SourceOut] = {}
    for step in tool_trace:
        if step.get("name") != "search_documents":
            continue
        res = step.get("result")
        if not isinstance(res, dict) or not res.get("ok"):
            continue
        for h in res.get("hits") or []:
            if not isinstance(h, dict):
                continue
            try:
                cid = UUID(str(h.get("chunk_id")))
                doc_id = UUID(str(h.get("document_id")))
            except (TypeError, ValueError):
                continue
            sc = float(h.get("score", 0.0))
            excerpt = str(h.get("excerpt", ""))
            title = str(h.get("title", ""))
            prev = best.get(cid)
            if prev is None or sc > prev.score:
                best[cid] = SourceOut(
                    chunk_id=cid,
                    document_id=doc_id,
                    title=title,
                    score=sc,
                    excerpt=excerpt,
                )
    return sorted(best.values(), key=lambda s: (-s.score, str(s.chunk_id)))


def weak_evidence_from_tool_trace(tool_trace: list[dict[str, Any]]) -> bool:
    searches = [
        s["result"]
        for s in tool_trace
        if s.get("name") == "search_documents"
        and isinstance(s.get("result"), dict)
        and s["result"].get("ok") is True
    ]
    if not searches:
        return True
    return all(s.get("weak_evidence", True) for s in searches)


def retrieved_context_records(tool_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Explicit retrieval payload for workflow state / tracing (deduped by chunk_id, best score wins).
    """
    best: dict[str, dict[str, Any]] = {}
    for step in tool_trace:
        if step.get("name") != "search_documents":
            continue
        res = step.get("result")
        if not isinstance(res, dict) or not res.get("ok"):
            continue
        for h in res.get("hits") or []:
            if not isinstance(h, dict):
                continue
            cid = h.get("chunk_id")
            if cid is None:
                continue
            key = str(cid)
            sc = float(h.get("score", 0.0))
            prev = best.get(key)
            if prev is None or sc > float(prev.get("score", 0.0)):
                best[key] = {
                    "chunk_id": str(cid),
                    "document_id": str(h.get("document_id", "")),
                    "title": str(h.get("title", "")),
                    "score": sc,
                    "excerpt": str(h.get("excerpt", "")),
                    "weak_evidence": bool(res.get("weak_evidence", True)),
                }
    return sorted(best.values(), key=lambda r: (-float(r["score"]), r["chunk_id"]))


def tool_trace_has_errors(tool_trace: list[dict[str, Any]]) -> bool:
    for step in tool_trace:
        r = step.get("result")
        if isinstance(r, dict) and r.get("error"):
            return True
    return False


def confidence_hint(
    *,
    weak_evidence: bool,
    tool_trace: list[dict[str, Any]],
) -> str:
    if tool_trace_has_errors(tool_trace):
        return "tool_errors"
    if weak_evidence:
        return "low_evidence"
    return "ok"
