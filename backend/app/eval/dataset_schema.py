"""Pydantic models for evaluation datasets (JSON on disk)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Expectations(BaseModel):
    """Per-case checks — all optional; runner only evaluates fields that are set."""

    groundedness_min: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum token-overlap score between answer and grounding_corpus.",
    )
    answer_must_mention: list[str] = Field(
        default_factory=list,
        description="Case-insensitive substrings that must appear in the answer.",
    )
    escalation_level: str | None = None
    structured_required_fields: list[str] = Field(
        default_factory=list,
        description="Keys expected on the structured payload (e.g. action_items).",
    )


class EvalCase(BaseModel):
    id: str
    grounding_corpus: str = Field(
        default="",
        description="Simulated retrieval text (excerpts) for groundedness scoring.",
    )
    expectations: Expectations = Field(default_factory=Expectations)
    model_output: dict[str, Any] = Field(
        default_factory=dict,
        description="Fixture output (Support Intelligence JSON) for offline runs.",
    )


class EvalDataset(BaseModel):
    version: Literal[1] = 1
    name: str = "unnamed"
    cases: list[EvalCase]


class CaseEvalResult(BaseModel):
    case_id: str
    passed: bool
    metrics: dict[str, Any] = Field(default_factory=dict)
    failures: list[str] = Field(default_factory=list)


class DatasetEvalResult(BaseModel):
    dataset: str
    cases_passed: int
    cases_total: int
    case_results: list[CaseEvalResult]
