"""Server-side speech-to-text via OpenAI Whisper (reliable baseline for voice input)."""

from __future__ import annotations

import re
from io import BytesIO

from openai import AsyncOpenAI


def _normalize_whisper_language(code: str | None) -> str | None:
    """Map e.g. zh-CN → zh so Whisper gets a stable ISO-639-1 hint (helps Chinese vs UI locale)."""
    if not code:
        return None
    s = str(code).strip()
    if not s:
        return None
    primary = s.replace("_", "-").split("-", 1)[0].lower()
    if len(primary) < 2 or not primary.isalpha():
        return None
    return primary[:2]


def _transcript_likely_garbage(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if len(t) == 1:
        # Single CJK character can be valid; lone punctuation is not.
        return not ("\u4e00" <= t <= "\u9fff")
    # Dots-only / punctuation-only (common on silence or broken WebM)
    if re.fullmatch(r"[\s.!?…。、，]+", t):
        return True
    if t in {".", "..", "...", "。。", "??", "？？"}:
        return True
    return False


def _transcript_whisper_hallucination(text: str) -> bool:
    """
    Whisper often emits stock subtitle / outro phrases when the clip is silent or unusable.
    Reject so we don't show nonsense as the user's words.
    """
    t = text.strip()
    low = t.lower()
    needles = (
        "amara.org",
        "由 amara",
        "社群提供的字幕",
        "字幕由",
        "谢谢观看",
        "感谢观看",
        "thanks for watching",
        "thank you for watching",
        "subscribe to",
    )
    for n in needles:
        has_cjk = any("\u4e00" <= c <= "\u9fff" for c in n)
        if has_cjk:
            if n in t:
                return True
        elif n in low:
            return True
    return False


async def transcribe_audio_bytes(
    *,
    api_key: str,
    audio: bytes,
    filename: str,
    model: str = "whisper-1",
    language: str | None = None,
) -> str:
    """
    Transcribe raw audio bytes. Filename extension helps Whisper infer container/codec.
    Optional `language` (ISO-639-1) improves accuracy when the UI locale differs from speech.
    """
    if not audio:
        raise ValueError("Empty audio payload.")
    if len(audio) < 256:
        raise ValueError("Audio clip is too small; try recording a bit longer.")
    client = AsyncOpenAI(api_key=api_key)
    buf = BytesIO(audio)
    buf.name = filename or "audio.webm"
    kwargs: dict = {
        "model": model,
        "file": buf,
        "temperature": 0,
    }
    lang = _normalize_whisper_language(language)
    if lang:
        kwargs["language"] = lang
    result = await client.audio.transcriptions.create(**kwargs)
    text = (result.text or "").strip()
    if not text:
        raise ValueError("Transcription returned empty text.")
    if _transcript_likely_garbage(text):
        raise ValueError(
            "Could not recognize clear speech. Speak closer to the mic, "
            "record at least one full sentence, or set your browser/OS language to Chinese "
            "if you are speaking Chinese.",
        )
    if _transcript_whisper_hallucination(text):
        raise ValueError(
            "The model returned a generic subtitle-like line instead of your speech — "
            "this usually means the recording was too quiet, silent, or the wrong mic was used. "
            "Raise the microphone input level in Windows sound settings, speak closer, "
            "and record again (several seconds).",
        )
    return text
