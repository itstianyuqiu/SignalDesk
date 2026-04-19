"""
RAG prompt construction — kept separate from HTTP routes for testing and evolution
(tool calls, workflows, alternate policies).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.retrieval import RetrievedChunk


@dataclass(frozen=True)
class RAGPromptBundle:
    """Structured pieces passed to the model; `user_input` is the Responses API `input` string."""

    instructions: str
    user_input: str


def build_rag_prompt_bundle(
    *,
    user_question: str,
    history_lines: list[str],
    chunks: list[RetrievedChunk],
    weak_evidence: bool,
) -> RAGPromptBundle:
    """
    Build safe instructions + a single user turn string.
    Grounding passages are numbered; the model must not invent passage IDs.
    """
    passages: list[str] = []
    for i, ch in enumerate(chunks, start=1):
        excerpt = ch.content.strip().replace("\r\n", "\n")
        if len(excerpt) > 4000:
            excerpt = excerpt[:4000] + "\n…"
        passages.append(
            f"[{i}] title={ch.title!r} chunk_id={ch.chunk_id} score={ch.score:.3f}\n{excerpt}",
        )

    passages_block = "\n\n".join(passages) if passages else "(no passages retrieved)"

    history_block = "\n".join(history_lines) if history_lines else "(no prior turns)"

    instructions = (
        "You are a careful support assistant for the Support Intelligence Platform.\n"
        "Answer using ONLY the numbered grounding passages below when they are relevant.\n"
        "- If passages are missing or weak, say clearly that the knowledge base does not "
        "contain enough evidence and suggest what the user could try next (e.g. upload docs, rephrase).\n"
        "- Do NOT fabricate chunk_ids, titles, or quotes. Do NOT claim a fact is in a passage unless it is.\n"
        "- Keep answers concise and professional.\n"
    )
    if weak_evidence:
        instructions += (
            "\nNOTE: Evidence quality is LOW for this request — explicitly state uncertainty "
            "and avoid definitive claims.\n"
        )

    user_input = (
        f"Recent conversation (oldest first):\n{history_block}\n\n"
        f"Grounding passages (use only these; ids are for traceability, not for user display):\n"
        f"{passages_block}\n\n"
        f"User question:\n{user_question.strip()}\n"
    )

    return RAGPromptBundle(instructions=instructions, user_input=user_input)
