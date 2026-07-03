from __future__ import annotations

import argparse
import json
from pathlib import Path

from sdetkit.pr_quality_adaptive_diagnosis import (
    ADAPTIVE_DIAGNOSIS_EXPORT_SCHEMA_VERSION,
    export_from_model,
    serialize_export,
)

SCHEMA_VERSION = ADAPTIVE_DIAGNOSIS_EXPORT_SCHEMA_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export the Adaptive Diagnosis contract as deterministic JSON."
    )
    parser.add_argument("--review-model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    model = json.loads(args.review_model.read_text(encoding="utf-8"))
    if not isinstance(model, dict):
        raise ValueError("review model must be a JSON object")
    payload = export_from_model(model)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(serialize_export(payload), encoding="utf-8", newline="\n")
    print("adaptive_diagnosis_json_export=passed")
    print(f"out={args.out.as_posix()}")
    print("reporting_only=true")
    print("automation_allowed=false")
    print("merge_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
