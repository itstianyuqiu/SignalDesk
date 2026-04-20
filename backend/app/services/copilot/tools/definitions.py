"""
OpenAI Responses API function tool definitions (isolated, reusable).

These dicts match `FunctionToolParam`: type=function, name, description, parameters, strict.
"""

from __future__ import annotations

from typing import Any

# JSON Schema objects for `parameters` (OpenAI function tools).
_SEARCH_DOCUMENTS_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "Natural language search over embedded chunks. Use the same language as the user when possible; "
                "repeat or paraphrase key terms. For mixed KBs, you may run a second search in English or Chinese."
            ),
        },
        "top_k": {
            "type": "integer",
            "description": "How many chunks to return (1–16). Default 8.",
            "minimum": 1,
            "maximum": 16,
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}

_GET_CASE_SUMMARY_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "case_id": {
            "type": "string",
            "description": "UUID of the case to summarize.",
        },
    },
    "required": ["case_id"],
    "additionalProperties": False,
}

_EXTRACT_ACTION_ITEMS_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "source_text": {
            "type": "string",
            "description": "Transcript, ticket body, or notes to extract tasks from.",
        },
        "max_items": {
            "type": "integer",
            "description": "Maximum bullet items to return (1–25).",
            "minimum": 1,
            "maximum": 25,
        },
    },
    "required": ["source_text"],
    "additionalProperties": False,
}

_DRAFT_SUPPORT_REPLY_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issue_summary": {
            "type": "string",
            "description": "Short description of the customer issue and desired outcome.",
        },
        "tone": {
            "type": "string",
            "enum": ["professional", "empathetic", "brief"],
            "description": "Voice for the draft reply.",
        },
        "recipient_name": {
            "type": "string",
            "description": "Optional customer name for salutation.",
        },
    },
    "required": ["issue_summary"],
    "additionalProperties": False,
}


def copilot_function_tools() -> list[dict[str, Any]]:
    """Tool definitions passed to `client.responses.create(..., tools=...)`."""
    return [
        {
            "type": "function",
            "name": "search_documents",
            "description": (
                "Search the user's uploaded/indexed documents using semantic retrieval. "
                "Call this when you need factual grounding from the knowledge base."
            ),
            "parameters": _SEARCH_DOCUMENTS_PARAMETERS,
            "strict": True,
        },
        {
            "type": "function",
            "name": "get_case_summary",
            "description": (
                "Load a support case record and recent conversation messages tied to that case. "
                "Requires a valid case UUID the current user is allowed to access."
            ),
            "parameters": _GET_CASE_SUMMARY_PARAMETERS,
            "strict": True,
        },
        {
            "type": "function",
            "name": "extract_action_items",
            "description": (
                "Extract concrete follow-ups / action items from free-form support text. "
                "Use after you have the text (from the user or from case history)."
            ),
            "parameters": _EXTRACT_ACTION_ITEMS_PARAMETERS,
            "strict": True,
        },
        {
            "type": "function",
            "name": "draft_support_reply",
            "description": (
                "Draft a customer-facing support reply from an issue summary. "
                "Does not search documents; pair with search_documents when policy or facts are needed."
            ),
            "parameters": _DRAFT_SUPPORT_REPLY_PARAMETERS,
            "strict": True,
        },
    ]
