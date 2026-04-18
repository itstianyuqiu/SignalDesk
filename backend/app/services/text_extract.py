"""Plain text and PDF text extraction (extensible for more formats)."""

from io import BytesIO

from pypdf import PdfReader


class UnsupportedContentTypeError(ValueError):
    pass


def extract_text(*, content: bytes, filename: str, content_type: str | None) -> tuple[str, str]:
    """
    Returns (normalized_text, detected_kind) where kind is 'text/plain' or 'application/pdf'.
    """
    ct = (content_type or "").split(";")[0].strip().lower()
    name = filename.lower()

    if ct in ("text/plain", "application/json") or name.endswith((".txt", ".md", ".csv", ".log")):
        return _decode_plain(content), "text/plain"

    if ct == "application/pdf" or name.endswith(".pdf"):
        return _extract_pdf(content), "application/pdf"

    # Heuristic: try UTF-8 decode if small header looks textual
    if not ct or ct == "application/octet-stream":
        if name.endswith(".txt") or _looks_like_text(content[:4096]):
            return _decode_plain(content), "text/plain"

    raise UnsupportedContentTypeError(
        f"Unsupported type '{content_type}' for '{filename}'. "
        "Phase 2 supports plain text and PDF.",
    )


def _looks_like_text(sample: bytes) -> bool:
    if not sample:
        return True
    printable = sum(1 for b in sample if 32 <= b < 127 or b in (9, 10, 13))
    return printable / max(len(sample), 1) > 0.85


def _decode_plain(content: bytes) -> str:
    return content.decode("utf-8", errors="replace").replace("\x00", "")


def _extract_pdf(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    parts: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        t = t.strip()
        if t:
            parts.append(t)
    text = "\n\n".join(parts).strip()
    if not text:
        raise ValueError("PDF contained no extractable text (may be scanned images).")
    return text
