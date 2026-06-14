from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sdetkit.diagnostic_queue_runner import (
    run_bounded_diagnostic_queue,
)

SCHEMA_VERSION = "sdetkit.diagnostic_queue_runner_cli.v1"

JsonObject = dict[str, Any]


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("max-jobs must be a positive integer") from exc

    if parsed < 1:
        raise argparse.ArgumentTypeError("max-jobs must be a positive integer")

    return parsed


def parse_args(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded local diagnostic job queue and emit a deterministic JSON summary."
        )
    )

    parser.add_argument(
        "--queue-path",
        required=True,
        help="Path to the local diagnostic queue JSON file.",
    )
    parser.add_argument(
        "--out-root",
        required=True,
        help="Directory for diagnostic worker output artifacts.",
    )
    parser.add_argument(
        "--input-root",
        required=True,
        help="Root directory for relative evidence input paths.",
    )
    parser.add_argument(
        "--max-jobs",
        required=True,
        type=_positive_integer,
        help="Maximum number of pending jobs to attempt.",
    )
    parser.add_argument(
        "--claimed-at",
        required=True,
        help="Explicit deterministic queue claim timestamp.",
    )
    parser.add_argument(
        "--finished-at",
        required=True,
        help="Explicit deterministic queue completion timestamp.",
    )

    return parser.parse_args(list(argv) if argv is not None else None)


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _decision_boundary() -> JsonObject:
    return {
        "automation_allowed": False,
        "automatic_retry": False,
        "proof_commands_executed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _error_summary(exc: Exception) -> JsonObject:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error": {
            "exception_type": type(exc).__name__,
            "message": _string(exc) or type(exc).__name__,
        },
        "decision_boundary": _decision_boundary(),
        "execution": {
            "automatic_retry": False,
            "proof_commands_executed": False,
            "patch_attempted": False,
            "merge_authorized": False,
        },
    }


def main(
    argv: Sequence[str] | None = None,
) -> int:
    args = parse_args(argv)

    try:
        result = run_bounded_diagnostic_queue(
            Path(args.queue_path),
            max_jobs=args.max_jobs,
            claimed_at=args.claimed_at,
            finished_at=args.finished_at,
            out_root=Path(args.out_root),
            input_root=Path(args.input_root),
        )
    except Exception as exc:
        print(
            json.dumps(
                _error_summary(exc),
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
