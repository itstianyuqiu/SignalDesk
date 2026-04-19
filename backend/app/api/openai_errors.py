"""Map OpenAI SDK errors to FastAPI HTTP responses."""

from fastapi import HTTPException
from openai import APIError, APIStatusError


def raise_http_from_openai(exc: APIError) -> None:
    """Raise HTTPException for OpenAI API failures; never returns."""
    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        raise HTTPException(
            status_code=429,
            detail=f"OpenAI rate limit or quota exceeded: {exc.message}",
        ) from exc
    if isinstance(exc, APIStatusError) and exc.status_code in (401, 403):
        raise HTTPException(
            status_code=502,
            detail="OpenAI API rejected the request (check OPENAI_API_KEY).",
        ) from exc
    raise HTTPException(
        status_code=502,
        detail=f"OpenAI request failed: {exc.message}",
    ) from exc
