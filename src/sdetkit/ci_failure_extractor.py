from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.ci_failure_extractor.v1"
DEFAULT_OUT = "build/sdetkit/failed-check-logs.json"

PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:py|md|yml|yaml|toml|ini|cfg|txt|sh))"
)
PYTEST_FAILED_RE = re.compile(r"^FAILED\s+(?P<nodeid>\S+)")
EXIT_CODE_RE = re.compile(r"(?:exit code|exited with code)\s+(?P<code>\d+)", re.IGNORECASE)


def _text(value: object) -> str:
    return str(value or "").strip()


def _first_nonempty(*values: object) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _extract_exit_code(lines: Sequence[str]) -> int | str:
    for line in reversed(lines):
        match = EXIT_CODE_RE.search(line)
        if match:
            return int(match.group("code"))
    return "unknown"


def _extract_command(lines: Sequence[str], failure_index: int) -> str:
    for line in reversed(lines[: max(failure_index, 0)]):
        stripped = line.strip()
        if stripped.startswith("Run "):
            return stripped.removeprefix("Run ").strip()
        if stripped.startswith("$ "):
            return stripped[2:].strip()
        if "python -m " in stripped or "pytest" in stripped or "mypy" in stripped:
            return stripped
    return "unknown"


def _failure_signal_index(lines: Sequence[str]) -> int:
    generic_index = -1
    for index, line in enumerate(lines):
        stripped = line.strip()
        lower = stripped.lower()

        if not stripped:
            continue
        if "process completed with exit code" in lower:
            generic_index = index
            continue
        if stripped.startswith("FAILED "):
            return index
        if re.search(r":[0-9]+:\s+error:", stripped):
            return index
        if "ruff format" in lower and "failed" in lower:
            return index
        if "would be reformatted" in lower:
            return index
        if "resolutionimpossible" in lower or "no matching distribution found" in lower:
            return index
        if "merge conflict" in lower or stripped.startswith("CONFLICT "):
            return index
        if stripped.startswith("ERROR ") or stripped.startswith("ERROR:"):
            return index

    return generic_index if generic_index >= 0 else 0


def _classify(line: str, full_text: str) -> tuple[str, str, bool, bool, str]:
    haystack = f"{line}\n{full_text}".lower()

    if "merge conflict" in haystack or "<<<<<<<" in haystack or "conflict " in haystack:
        return "workflow", "merge_conflict", False, True, "Merge conflict requires human review"

    if "ruff format" in haystack or "would be reformatted" in haystack:
        return "formatting", "formatter_only", True, False, ""

    if "ruff" in haystack and ("failed" in haystack or "error" in haystack):
        return "formatting", "lint", False, False, ""

    if "mypy" in haystack or re.search(r":[0-9]+:\s+error:", line):
        return "type_contract", "type", False, True, "Type contract failures are review-first"

    if line.strip().startswith("FAILED ") or "pytest" in haystack or "assertionerror" in haystack:
        return "test", "test", False, False, ""

    if "resolutionimpossible" in haystack or "no matching distribution found" in haystack:
        return (
            "dependency",
            "dependency",
            False,
            True,
            "Dependency failures require review-first alignment",
        )

    return "unknown", "unknown", False, True, "Unknown failure requires log review"


def _affected_files(line: str) -> list[str]:
    paths = {match.group("path") for match in PATH_RE.finditer(line)}
    node_match = PYTEST_FAILED_RE.match(line.strip())
    if node_match:
        node_id = node_match.group("nodeid")
        file_part = node_id.split("::", 1)[0]
        if file_part:
            paths.add(file_part)
    return sorted(paths)


def _failing_test(line: str) -> str:
    match = PYTEST_FAILED_RE.match(line.strip())
    return match.group("nodeid") if match else "unknown"


def extract_log_text(
    text: str,
    *,
    check_name: str = "raw-ci-log",
    log_path: str = "",
) -> dict[str, Any]:
    lines = text.splitlines()
    failure_index = _failure_signal_index(lines)
    first_line = lines[failure_index].strip() if lines else "no log lines found"
    surface, failure_class, safe_to_auto_fix, review_first, reason = _classify(first_line, text)
    affected_files = _affected_files(first_line)
    command = _extract_command(lines, failure_index)
    exit_code = _extract_exit_code(lines)

    if not affected_files and failure_class == "unknown":
        affected_files = []

    title_by_class = {
        "formatter_only": "Formatter-only failure extracted from CI log",
        "lint": "Lint failure extracted from CI log",
        "type": "Type contract failure extracted from CI log",
        "test": "Test failure extracted from CI log",
        "dependency": "Dependency failure extracted from CI log",
        "merge_conflict": "Merge conflict extracted from CI log",
        "unknown": "Unknown failure extracted from CI log",
    }

    record: dict[str, Any] = {
        "name": check_name,
        "check": check_name,
        "command": command,
        "exit_code": exit_code,
        "log_path": log_path,
        "first_failure_line": first_line,
        "first_failure": {
            "line": first_line,
            "line_number": failure_index + 1 if lines else 0,
            "tool": _first_nonempty(failure_class, "unknown"),
            "kind": failure_class,
        },
        "diagnosis": {
            "title": title_by_class.get(failure_class, "Failure extracted from CI log"),
            "surface": surface,
            "confidence": "medium" if failure_class != "unknown" else "low",
        },
        "failure_class": failure_class,
        "affected_files": affected_files,
        "failing_file": affected_files[0] if affected_files else "unknown",
        "failing_test": _failing_test(first_line),
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
    }
    return record


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.ci_failure_extractor")
    parser.add_argument("--log", action="append", required=True, help="Raw CI log file to extract")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        payload = write_failed_check_logs(args.log, args.out)
    except OSError as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"failed_check_logs_json={args.out}")
        print(f"failed_check_count={payload['failed_check_count']}")
        print(f"safe_to_auto_fix_count={payload['summary']['safe_to_auto_fix_count']}")
        print(f"review_first_count={payload['summary']['review_first_count']}")
        print(f"unknown_count={payload['summary']['unknown_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
