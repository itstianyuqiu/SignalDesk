"""Thin wrapper around OpenAI Responses API (easy to mock / extend)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI


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
