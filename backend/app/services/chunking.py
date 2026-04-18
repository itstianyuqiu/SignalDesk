"""Character-based chunking with overlap (token-aware splitting can be swapped in later)."""


def chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    normalized = text.strip()
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    n = len(normalized)
    while start < n:
        end = min(start + chunk_size, n)
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks
