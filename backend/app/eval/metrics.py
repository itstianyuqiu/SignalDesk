"""
Pluggable evaluation metrics for copilot structured outputs.

Extend `EvalMetric` with new classes (e.g. LLM-as-judge, embedding similarity).
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from app.services.copilot.tools.schemas import SupportIntelligenceStructured


class MetricScore(BaseModel):
    name: str
    value: float | bool
    details: dict[str, Any] = Field(default_factory=dict)


class EvalMetric(Protocol):
    name: str

    def score(self, *, grounding_corpus: str, output: dict[str, Any]) -> MetricScore: ...


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1}


class GroundednessOverlap:
    """
    Lexical overlap between the answer and grounding_corpus (Jaccard on word tokens).

    Why: cheap proxy for "sticks to provided evidence" before you add LLM judges.
    """

    name = "groundedness_token_jaccard"

    def score(self, *, grounding_corpus: str, output: dict[str, Any]) -> MetricScore:
        answer = str(output.get("answer") or "")
        a = _tokenize(answer)
        g = _tokenize(grounding_corpus)
        if not a or not g:
            j = 0.0
        else:
            inter = len(a & g)
            union = len(a | g)
            j = inter / union if union else 0.0
        return MetricScore(name=self.name, value=j, details={"answer_tokens": len(a), "ground_tokens": len(g)})


class CitationPresence:
    """
    Ensures the answer mentions expected phrases (simulating citation to titles/snippets).

    Why: enforces that the model references retrieved material by name or quote.
    """

    name = "citation_phrases_present"

    def __init__(self, phrases: list[str]) -> None:
        self.phrases = [p.strip() for p in phrases if p.strip()]

    def score(self, *, grounding_corpus: str, output: dict[str, Any]) -> MetricScore:
        answer = str(output.get("answer") or "").lower()
        missing = [p for p in self.phrases if p.lower() not in answer]
        ok = len(missing) == 0
        return MetricScore(
            name=self.name,
            value=ok,
            details={"required": self.phrases, "missing": missing},
        )


class StructuredFormat:
    """
    Validates JSON against `SupportIntelligenceStructured` (schema used in production).

    Why: catches regressions in required keys, enums, and types after prompt changes.
    """

    name = "structured_format_valid"

    def score(self, *, grounding_corpus: str, output: dict[str, Any]) -> MetricScore:
        try:
            SupportIntelligenceStructured.model_validate(output)
            return MetricScore(name=self.name, value=True, details={})
        except ValidationError as exc:
            return MetricScore(name=self.name, value=False, details={"errors": exc.errors()})


class EscalationMatch:
    """Optional: expected escalation.level in structured output."""

    name = "escalation_level_match"

    def __init__(self, expected: str | None) -> None:
        self.expected = expected

    def score(self, *, grounding_corpus: str, output: dict[str, Any]) -> MetricScore:
        if self.expected is None:
            return MetricScore(name=self.name, value=True, details={"skipped": True})
        esc = output.get("escalation") if isinstance(output.get("escalation"), dict) else {}
        got = str(esc.get("level") or "")
        ok = got == self.expected
        return MetricScore(name=self.name, value=ok, details={"expected": self.expected, "got": got})


class RequiredStructuredFields:
    """Checks presence of top-level keys (lightweight contract test)."""

    name = "structured_required_fields"

    def __init__(self, fields: list[str]) -> None:
        self.fields = fields

    def score(self, *, grounding_corpus: str, output: dict[str, Any]) -> MetricScore:
        missing = [f for f in self.fields if f not in output]
        ok = len(missing) == 0
        return MetricScore(name=self.name, value=ok, details={"missing": missing})
