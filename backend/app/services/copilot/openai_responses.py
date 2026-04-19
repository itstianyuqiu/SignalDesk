"""Thin wrapper around OpenAI Responses API (easy to mock / extend)."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from app.services.copilot.tools.context import ToolContext
from app.services.copilot.tools.definitions import copilot_function_tools
from app.services.copilot.tools.executor import execute_tool
from app.services.copilot.tools.schemas import EscalationStructured, SupportIntelligenceStructured

logger = logging.getLogger(__name__)

# Structured output schema for the final support intelligence payload (strict JSON Schema subset).
_SUPPORT_INTELLIGENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "Primary user-visible reply (plain text or light markdown).",
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "owner": {"type": "string"},
                },
                "required": ["title", "priority"],
                "additionalProperties": False,
            },
        },
        "escalation": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["none", "tier1", "tier2", "engineering", "leadership"],
                },
                "rationale": {"type": "string"},
            },
            "required": ["level", "rationale"],
            "additionalProperties": False,
        },
        "support_reply_draft": {"type": "string"},
    },
    "required": ["answer", "action_items", "escalation"],
    "additionalProperties": False,
}


def _extract_output_text(response: object) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    # Fallback: walk output items (SDK shape may vary by version)
    out = getattr(response, "output", None) or []
    parts: list[str] = []
    for item in out:
        content = getattr(item, "content", None) or []
        for block in content:
            t = getattr(block, "text", None)
            if isinstance(t, str):
                parts.append(t)
            elif isinstance(block, dict):
                txt = block.get("text")
                if isinstance(txt, str):
                    parts.append(txt)
    return "\n".join(parts).strip()


async def generate_answer(
    *,
    api_key: str,
    model: str,
    instructions: str,
    user_input: str,
) -> str:
    client = AsyncOpenAI(api_key=api_key)
    response = await client.responses.create(
        model=model,
        instructions=instructions,
        input=user_input,
    )
    return _extract_output_text(response)


def _event_type(event: object) -> str:
    if isinstance(event, dict):
        t = event.get("type")
        return t if isinstance(t, str) else ""
    t = getattr(event, "type", None)
    return t if isinstance(t, str) else ""


def _stream_event_text_delta(event: object) -> str | None:
    """Extract incremental assistant-visible text from Responses API stream events."""
    et = _event_type(event)
    if not et:
        return None

    # Skip tool / argument streams that also use `delta`
    if any(
        x in et
        for x in (
            "function_call_arguments",
            "custom_tool_call",
            "mcp_call",
            "code_interpreter",
            "file_search",
        )
    ):
        return None

    # Assistant-visible tokens only (see response_text_delta_event.type)
    if et != "response.output_text.delta" and not et.endswith("output_text.delta"):
        return None

    if isinstance(event, dict):
        delta = event.get("delta")
    else:
        delta = getattr(event, "delta", None)

    if isinstance(delta, str) and delta:
        return delta
    if isinstance(delta, dict):
        t = delta.get("text")
        if isinstance(t, str) and t:
            return t
    return None


async def stream_answer(
    *,
    api_key: str,
    model: str,
    instructions: str,
    user_input: str,
) -> AsyncIterator[str]:
    client = AsyncOpenAI(api_key=api_key)
    stream = await client.responses.create(
        model=model,
        instructions=instructions,
        input=user_input,
        stream=True,
    )
    emitted = 0
    completed_response: object | None = None
    async for event in stream:
        if _event_type(event) == "response.completed":
            completed_response = (
                event.get("response") if isinstance(event, dict) else getattr(event, "response", None)
            )
        chunk = _stream_event_text_delta(event)
        if chunk:
            emitted += 1
            yield chunk

    # If delta events were not recognized but the stream completed, send full text once.
    if emitted == 0 and completed_response is not None:
        full = _extract_output_text(completed_response)
        if full:
            yield full


@dataclass(frozen=True)
class ToolAgentResult:
    """Retrieval is not run here — only tool calls orchestrated by the model."""

    interim_assistant_text: str
    tool_trace: list[dict[str, Any]]


async def run_tool_agent_loop(
    *,
    api_key: str,
    model: str,
    instructions: str,
    user_input: str,
    ctx: ToolContext,
    max_rounds: int = 10,
) -> ToolAgentResult:
    """
    Run OpenAI function tools until the model stops requesting tools.
    Separation: this layer talks to OpenAI; `execute_tool` performs retrieval/DB/LLM helpers.
    """
    client = AsyncOpenAI(api_key=api_key)
    tools = copilot_function_tools()
    tool_trace: list[dict[str, Any]] = []
    previous_response_id: str | None = None
    next_input: str | list[dict[str, Any]] = user_input

    for _ in range(max_rounds):
        kwargs: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "tools": tools,
            "parallel_tool_calls": True,
        }
        if previous_response_id is None:
            kwargs["input"] = next_input
        else:
            kwargs["previous_response_id"] = previous_response_id
            kwargs["input"] = next_input

        response = await client.responses.create(**kwargs)
        previous_response_id = response.id

        calls: list[Any] = [
            it for it in (response.output or []) if getattr(it, "type", None) == "function_call"
        ]
        if not calls:
            return ToolAgentResult(
                interim_assistant_text=_extract_output_text(response),
                tool_trace=tool_trace,
            )

        outputs: list[dict[str, Any]] = []
        for call in calls:
            name = getattr(call, "name", "") or ""
            raw_args = getattr(call, "arguments", "") or ""
            call_id = getattr(call, "call_id", "") or ""
            result_obj = await execute_tool(name, raw_args, ctx)
            tool_trace.append(
                {
                    "name": name,
                    "call_id": call_id,
                    "arguments": raw_args,
                    "result": result_obj,
                },
            )
            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result_obj, default=str),
                },
            )
        next_input = outputs

    logger.warning("copilot_tool_loop_max_rounds", extra={"max_rounds": max_rounds})
    return ToolAgentResult(interim_assistant_text="", tool_trace=tool_trace)


async def synthesize_support_intelligence(
    *,
    api_key: str,
    model: str,
    user_question: str,
    interim_assistant_text: str,
    tool_trace: list[dict[str, Any]],
) -> SupportIntelligenceStructured:
    """
    Structured output pass: consolidates tool results into validated support intelligence.
    Runs after tool execution — separation from retrieval and tool dispatch.
    """
    client = AsyncOpenAI(api_key=api_key)
    payload = {
        "user_question": user_question.strip(),
        "tool_trace": tool_trace,
        "interim_assistant_analysis": interim_assistant_text.strip(),
    }
    response = await client.responses.create(
        model=model,
        instructions=(
            "You produce the final Support Intelligence JSON for the UI. "
            "Use tool_trace results as authoritative when present. "
            "Do not invent case ids, chunk ids, or document titles. "
            "If evidence is missing, say so in the answer and keep escalation conservative."
        ),
        input=json.dumps(payload, default=str),
        text={
            "format": {
                "type": "json_schema",
                "name": "support_intelligence",
                "strict": True,
                "schema": _SUPPORT_INTELLIGENCE_SCHEMA,
            }
        },
    )
    raw = _extract_output_text(response)
    try:
        return SupportIntelligenceStructured.model_validate_json(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("structured_synthesis_parse_failed", extra={"err": str(exc)})
        return SupportIntelligenceStructured(
            answer=interim_assistant_text.strip()
            or "I could not produce a structured summary; see tool results in metadata.",
            action_items=[],
            escalation=EscalationStructured(
                level="none",
                rationale="Structured synthesis unavailable.",
            ),
            support_reply_draft=None,
        )
