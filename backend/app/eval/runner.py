"""Load a dataset JSON and score each case with the built-in metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval.dataset_schema import CaseEvalResult, DatasetEvalResult, EvalCase, EvalDataset
from app.eval.metrics import (
    CitationPresence,
    EscalationMatch,
    GroundednessOverlap,
    RequiredStructuredFields,
    StructuredFormat,
)


def load_dataset(path: Path) -> EvalDataset:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return EvalDataset.model_validate(raw)


def evaluate_case(case: EvalCase) -> CaseEvalResult:
    out = case.model_output
    exp = case.expectations
    failures: list[str] = []
    metrics_flat: dict[str, Any] = {}

    g = GroundednessOverlap().score(grounding_corpus=case.grounding_corpus, output=out)
    metrics_flat[g.name] = g.value
    if exp.groundedness_min is not None and isinstance(g.value, float) and g.value < exp.groundedness_min:
        failures.append(
            f"groundedness {g.value:.3f} < min {exp.groundedness_min}",
        )

    cit = CitationPresence(exp.answer_must_mention).score(
        grounding_corpus=case.grounding_corpus,
        output=out,
    )
    metrics_flat[cit.name] = cit.value
    if exp.answer_must_mention and not cit.value:
        failures.append(f"citation phrases missing: {cit.details.get('missing')}")

    fmt = StructuredFormat().score(grounding_corpus=case.grounding_corpus, output=out)
    metrics_flat[fmt.name] = fmt.value
    if not fmt.value:
        failures.append("structured format validation failed")

    req = RequiredStructuredFields(exp.structured_required_fields).score(
        grounding_corpus=case.grounding_corpus,
        output=out,
    )
    metrics_flat[req.name] = req.value
    if exp.structured_required_fields and not req.value:
        failures.append(f"missing structured fields: {req.details.get('missing')}")

    esc = EscalationMatch(exp.escalation_level).score(
        grounding_corpus=case.grounding_corpus,
        output=out,
    )
    metrics_flat[esc.name] = esc.value
    if exp.escalation_level is not None and not esc.value:
        failures.append(
            f"escalation mismatch: expected {exp.escalation_level}, got {esc.details.get('got')}",
        )

    passed = len(failures) == 0
    return CaseEvalResult(
        case_id=case.id,
        passed=passed,
        metrics=metrics_flat,
        failures=failures,
    )


def run_dataset(path: Path) -> DatasetEvalResult:
    ds = load_dataset(path)
    results = [evaluate_case(c) for c in ds.cases]
    passed_n = sum(1 for r in results if r.passed)
    return DatasetEvalResult(
        dataset=ds.name,
        cases_passed=passed_n,
        cases_total=len(results),
        case_results=results,
    )
