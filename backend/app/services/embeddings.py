"""OpenAI embedding client (batch-friendly)."""

from openai import AsyncOpenAI

from app.core.config import Settings


async def embed_texts(
    texts: list[str],
    *,
    settings: Settings,
    batch_size: int = 64,
) -> list[list[float]]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    if not texts:
        return []

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        create_kwargs: dict = {
            "model": settings.embedding_model,
            "input": batch,
        }
        if settings.embedding_model.startswith("text-embedding-3"):
            create_kwargs["dimensions"] = settings.embedding_dimensions

        response = await client.embeddings.create(**create_kwargs)
        # Preserve input order
        data = sorted(response.data, key=lambda d: d.index)
        for row in data:
            out.append(list(row.embedding))
    return out
