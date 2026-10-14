from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sdetkit.failure_vector import render_failure_vector_bundle_report
from sdetkit.failure_vector_adapters import (
    build_ecosystem_failure_vector_bundle,
    extract_ecosystem_failure_vector,
)

SCHEMA_VERSION = "sdetkit.ci_failure_extractor.v1"
DEFAULT_OUT = "build/sdetkit/failed-check-logs.json"
DEFAULT_FAILURE_VECTORS_OUT = "build/sdetkit/failure-vectors.json"
DEFAULT_FAILURE_VECTORS_MD = "build/sdetkit/failure-vectors.md"

# Failure classes map onto the diagnostic-vector engine's surface vocabulary.
_SURFACE_BY_CLASS = {
    "formatter_only": "formatting",
    "lint": "formatting",
    "type": "type_contract",
    "test": "test",
    "dependency": "dependency",
    "merge_conflict": "workflow",
    "compile": "build",
    "link": "build",
}
_REVIEW_FIRST_REASONS = {
    "merge_conflict": "Merge conflict requires human review",
    "type": "Type contract failures are review-first",
    "dependency": "Dependency failures require review-first alignment",
    "unknown": "Unknown failure requires log review",
}
_TITLE_BY_CLASS = {
    "formatter_only": "Formatter-only failure extracted from CI log",
    "lint": "Lint failure extracted from CI log",
    "type": "Type contract failure extracted from CI log",
    "test": "Test failure extracted from CI log",
    "dependency": "Dependency failure extracted from CI log",
    "merge_conflict": "Merge conflict extracted from CI log",
    "compile": "Compile failure extracted from CI log",
    "link": "Link failure extracted from CI log",
    "unknown": "Unknown failure extracted from CI log",
}


def _line_number(lines: Sequence[str], first_line: str) -> int:
    target = first_line.strip()
    for index, line in enumerate(lines):
        if line.strip() == target:
            return index + 1
    return 1 if lines else 0


def _failing_test(vector: dict[str, Any], failure_class: str) -> str:
    if failure_class != "test":
        return "unknown"
    return str(vector.get("failing_test_or_check") or "unknown")


def extract_log_text(
    text: str,
    *,
    check_name: str = "raw-ci-log",
    log_path: str = "",
) -> dict[str, Any]:
    """Extract the first real failure through the shared multi-ecosystem engine."""

    lines = text.splitlines()
    result = extract_ecosystem_failure_vector(text, check=check_name, log_url=log_path or None)
    vector = result.to_dict()
    failure_class = str(vector["failure_class"])
    first_line = str(vector["first_failing_line"]).strip() or (
        "no log lines found" if not lines else lines[0].strip()
    )
    affected_files = [str(path) for path in vector["affected_files"]]  # type: ignore[union-attr]
    safe_to_auto_fix = failure_class == "formatter_only"
    review_first = failure_class in _REVIEW_FIRST_REASONS
    reason = _REVIEW_FIRST_REASONS.get(failure_class, "")
    exit_code = vector["exit_code"]

    return {
        "name": check_name,
        "check": check_name,
        "command": str(vector["command"] or "unknown"),
        "exit_code": exit_code if isinstance(exit_code, int) else "unknown",
        "log_path": log_path,
        "ecosystem": result.ecosystem,
        "first_failure_line": first_line,
        "first_failure": {
            "line": first_line,
            "line_number": _line_number(lines, first_line),
            "tool": result.tool if result.tool != "unknown" else failure_class,
            "kind": failure_class,
        },
        "diagnosis": {
            "title": _TITLE_BY_CLASS.get(failure_class, "Failure extracted from CI log"),
            "surface": _SURFACE_BY_CLASS.get(failure_class, "unknown"),
            "confidence": "medium" if failure_class != "unknown" else "low",
        },
        "failure_class": failure_class,
        "affected_files": affected_files,
        "failing_file": affected_files[0] if affected_files else "unknown",
        "failing_test": _failing_test(vector, failure_class),
        "safe_to_auto_fix": safe_to_auto_fix,
        "review_first": review_first,
        "safe_remediation": {
            "safe_to_auto_fix": safe_to_auto_fix,
            "strategy": "run_pre_commit"
            if safe_to_auto_fix
            else "review_first"
            if review_first
            else "rerun_focused_proof",
            "reason": reason,
        },
        "safety_gate": vector["safety_gate"],
    }


def build_failed_check_logs(log_paths: Sequence[str | Path]) -> dict[str, Any]:
    records = []
    for raw_path in log_paths:
        path = Path(raw_path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        records.append(
            extract_log_text(
                text,
                check_name=path.parent.name if path.parent.name else path.stem,
                log_path=path.as_posix(),
            )
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "failed_check_count": len(records),
        "failed_checks": records,
        "summary": {
            "safe_to_auto_fix_count": sum(1 for record in records if record["safe_to_auto_fix"]),
            "review_first_count": sum(1 for record in records if record["review_first"]),
            "unknown_count": sum(1 for record in records if record["failure_class"] == "unknown"),
        },
    }


def write_failed_check_logs(log_paths: Sequence[str | Path], out: str | Path) -> dict[str, Any]:
    payload = build_failed_check_logs(log_paths)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def write_failure_vector_artifacts(
    log_paths: Sequence[str | Path],
    *,
    json_out: str | Path = DEFAULT_FAILURE_VECTORS_OUT,
    markdown_out: str | Path | None = None,
    environment: str = "unknown",
) -> dict[str, Any]:
    payload = build_ecosystem_failure_vector_bundle(log_paths, environment=environment)
    json_path = Path(json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if markdown_out:
        md_path = Path(markdown_out)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_failure_vector_bundle_report(payload) + "\n", encoding="utf-8")

    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.ci_failure_extractor")
    parser.add_argument("--log", action="append", required=True, help="Raw CI log file to extract")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument(
        "--failure-vectors-out",
        default="",
        help=(
            "Optional JSON output path for deterministic failure-vector bundle "
            f"(defaults to {DEFAULT_FAILURE_VECTORS_OUT} when markdown output is requested)"
        ),
    )
    parser.add_argument(
        "--failure-vectors-md",
        default="",
        help="Optional Markdown output path for deterministic failure-vector bundle summary",
    )
    parser.add_argument("--environment", default="unknown")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        payload = write_failed_check_logs(args.log, args.out)
        vector_payload = None
        vectors_out = args.failure_vectors_out
        if args.failure_vectors_md and not vectors_out:
            vectors_out = DEFAULT_FAILURE_VECTORS_OUT
        if vectors_out:
            vector_payload = write_failure_vector_artifacts(
                args.log,
                json_out=vectors_out,
                markdown_out=args.failure_vectors_md or None,
                environment=args.environment,
            )
    except OSError as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        output: dict[str, Any] = {"failed_check_logs": payload}
        if vector_payload is not None:
            output["failure_vector_bundle"] = vector_payload
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(f"failed_check_logs_json={args.out}")
        print(f"failed_check_count={payload['failed_check_count']}")
        print(f"safe_to_auto_fix_count={payload['summary']['safe_to_auto_fix_count']}")
        print(f"review_first_count={payload['summary']['review_first_count']}")
        print(f"unknown_count={payload['summary']['unknown_count']}")
        if vector_payload is not None:
            print(f"failure_vectors_json={vectors_out}")
            if args.failure_vectors_md:
                print(f"failure_vectors_md={args.failure_vectors_md}")
            print(f"failure_vector_count={vector_payload['failure_vector_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
