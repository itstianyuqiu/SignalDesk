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


def build_copilot_tool_agent_bundle(
    *,
    user_question: str,
    history_lines: list[str],
    case_context_block: str | None = None,
) -> RAGPromptBundle:
    """
    Instructions for the tool-calling copilot (no pre-fetched passages — retrieval is `search_documents`).
    """
    history_block = "\n".join(history_lines) if history_lines else "(no prior turns)"

    instructions = (
        "You are a Support Intelligence copilot with function tools.\n"
        "Tools:\n"
        "- search_documents: semantic search over the user's indexed knowledge base. "
        "The system may also run a baseline search on the user's question; you should still call this tool "
        "with focused queries (synonyms, English+Chinese terms) when refining.\n"
        "- get_case_summary: load a case record and recent messages when a case UUID is known or the user "
        "asks about a specific case.\n"
        "- extract_action_items: turn transcripts or long notes into a short checklist of follow-ups.\n"
        "- draft_support_reply: draft a customer-facing reply from an issue summary (pair with "
        "search_documents if policy or product facts matter).\n"
        "Policies:\n"
        "- Prefer tools over guessing. Ground answers in search_documents results when they exist.\n"
        "- Match the user's language and domain (e.g. 邮轮/cruise vs 邮政/postal). Do not substitute an unrelated topic.\n"
        "- For search_documents `query`, use the same language as the user when possible; add a second query in "
        "another language if the knowledge base may be indexed in that language.\n"
        "- If the KB has no hits after search_documents, say evidence is thin.\n"
        "- Never invent chunk_ids, document titles, or case identifiers.\n"
        "- After you finish calling tools, write a concise internal analysis the operator can trust.\n"
        "The platform will merge your tool results into a structured summary separately.\n"
    )
    if case_context_block and case_context_block.strip():
        instructions += (
            "\n\n--- Active case context (treat as authoritative for this turn) ---\n"
            f"{case_context_block.strip()}\n"
            "--- End case context ---\n"
        )

    user_input = (
        f"Conversation (oldest first):\n{history_block}\n\n"
        f"User request:\n{user_question.strip()}\n"
    )
    return RAGPromptBundle(instructions=instructions, user_input=user_input)
