"""CLI: python -m app.eval.cli --dataset path/to/dataset.json"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run Support Intelligence eval dataset.")
    p.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parent / "datasets" / "example.json",
        help="Path to dataset JSON",
    )
    args = p.parse_args(argv)

    from app.eval.runner import run_dataset

    result = run_dataset(args.dataset)
    print(json.dumps(result.model_dump(), indent=2))
    return 0 if result.cases_passed == result.cases_total else 1


if __name__ == "__main__":
    raise SystemExit(main())
