from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.ci_failure_triage.v1"

PYTEST_NODE_RE = re.compile(r"FAILED\s+([A-Za-z0-9_./:-]+::[^\s]+)(?:\s+-\s+(.+))?")
MYPY_ERROR_RE = re.compile(r"^(.+?\.py):\d+:\s+error:\s+(.+)$", re.MULTILINE)
PYTHON_EXCEPTION_RE = re.compile(r"\b([A-Z][A-Za-z]+Error|Exception):\s*(.+)")
EXIT_CODE_RE = re.compile(r"Process completed with exit code (?!0\b)(\d+)")
FILE_PATH_RE = re.compile(r"\b(?:src|tests)/[A-Za-z0-9_./-]+\.py\b")


@dataclass(frozen=True)
class CiFailureTriageReport:
    schema_version: str
    classification: str
    blocker: bool
    headline_failure: str
    actual_failure: str
    root_cause_candidates: tuple[str, ...]
    likely_owner_files: tuple[str, ...]
    contract_that_failed: str
    noise_to_ignore: tuple[str, ...]
    recommended_fix_shape: str
    verification_commands: tuple[str, ...]
    confidence: str
    next_best_action: str


def _clean(value: object, *, limit: int = 260) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _unique(values: Sequence[str], *, limit: int = 8) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        item = _clean(value)
        if item and item not in out:
            out.append(item)
        if len(out) >= limit:
            break
    return tuple(out)


def _coverage_lines(lines: Sequence[str]) -> tuple[str, ...]:
    hits: list[str] = []
    for line in lines:
        lowered = line.lower()
        if "coverage" in lowered and any(
            token in lowered for token in ("fail", "under", "threshold", "required")
        ):
            hits.append(line)
    return _unique(hits, limit=3)


def _exit_lines(lines: Sequence[str]) -> tuple[str, ...]:
    return _unique([line for line in lines if EXIT_CODE_RE.search(line)], limit=3)


def _pytest_failure(text: str) -> tuple[str, str, str] | None:
    match = PYTEST_NODE_RE.search(text)
    if not match:
        return None
    node = _clean(match.group(1))
    detail = _clean(match.group(2) or "pytest node failed")
    owner = node.split("::", 1)[0]
    return node, detail, owner


def _mypy_failure(text: str) -> tuple[str, str] | None:
    match = MYPY_ERROR_RE.search(text)
    if not match:
        return None
    return _clean(match.group(1)), _clean(match.group(2))


def _python_exception(text: str) -> str:
    match = PYTHON_EXCEPTION_RE.search(text)
    if not match:
        return ""
    return _clean(f"{match.group(1)}: {match.group(2)}")


def _file_mentions(text: str) -> tuple[str, ...]:
    return _unique(FILE_PATH_RE.findall(text), limit=8)


def _as_payload(report: CiFailureTriageReport) -> dict[str, Any]:
    return asdict(report)


def build_triage_report(text: str) -> CiFailureTriageReport:
    lines = text.splitlines()
    coverage = _coverage_lines(lines)
    exits = _exit_lines(lines)
    pytest = _pytest_failure(text)
    mypy = _mypy_failure(text)
    exception = _python_exception(text)
    owners = list(_file_mentions(text))

    if pytest is not None:
        node, detail, owner = pytest
        if owner not in owners:
            owners.insert(0, owner)
        noise = []
        if coverage:
            noise.append("coverage wrapper reported after an earlier pytest failure")
        if exits:
            noise.append("nonzero process exit is a wrapper after the failing test")
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="test_failure",
            blocker=True,
            headline_failure=coverage[-1] if coverage else (exits[-1] if exits else node),
            actual_failure=f"{node} - {detail}",
            root_cause_candidates=(
                "the first failing pytest assertion is the real blocker",
                "later CI wrapper failures should not be patched first",
            ),
            likely_owner_files=_unique(owners),
            contract_that_failed="pytest behavior contract",
            noise_to_ignore=_unique(noise),
            recommended_fix_shape=(
                "Fix the failing pytest assertion or owner implementation before changing "
                "coverage, workflow, or quality gates."
            ),
            verification_commands=(f"python -m pytest -q {node} -o addopts=",),
            confidence="high",
            next_best_action=f"open {owner} and reproduce {node}",
        )

    if mypy is not None:
        owner, detail = mypy
        if owner not in owners:
            owners.insert(0, owner)
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="test_contract_failure",
            blocker=True,
            headline_failure=exits[-1] if exits else f"{owner}: {detail}",
            actual_failure=f"{owner}: {detail}",
            root_cause_candidates=("type/API contract mismatch",),
            likely_owner_files=_unique(owners),
            contract_that_failed="mypy type contract",
            noise_to_ignore=_unique(["nonzero process exit is a wrapper"] if exits else []),
            recommended_fix_shape="Fix the first type/API mismatch; do not broaden into style cleanup.",
            verification_commands=("python -m mypy src",),
            confidence="medium",
            next_best_action=f"inspect the first mypy error in {owner}",
        )

    if coverage:
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="quality_wrapper",
            blocker=True,
            headline_failure=coverage[-1],
            actual_failure=coverage[0],
            root_cause_candidates=("coverage gate reported below-threshold evidence",),
            likely_owner_files=_unique(owners),
            contract_that_failed="coverage policy",
            noise_to_ignore=_unique(["no earlier pytest node failure was found in the log"]),
            recommended_fix_shape=(
                "Inspect missed coverage or missing regression tests; do not lower the gate "
                "unless policy intentionally changed."
            ),
            verification_commands=("python -m pytest --cov",),
            confidence="medium",
            next_best_action="rerun coverage locally and inspect the first missed owner file",
        )

    if exception:
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="product_bug",
            blocker=True,
            headline_failure=exits[-1] if exits else exception,
            actual_failure=exception,
            root_cause_candidates=("Python exception raised during CI command",),
            likely_owner_files=_unique(owners),
            contract_that_failed="runtime command contract",
            noise_to_ignore=_unique(["nonzero process exit is a wrapper"] if exits else []),
            recommended_fix_shape="Reproduce the command path and patch the smallest owner module.",
            verification_commands=("python -m pytest -q <focused-test> -o addopts=",),
            confidence="medium",
            next_best_action="inspect the traceback owner file and add a focused regression test",
        )

    if exits:
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="ci_failure_real_flake",
            blocker=True,
            headline_failure=exits[-1],
            actual_failure=exits[0],
            root_cause_candidates=("nonzero CI exit found without a more specific parsed blocker",),
            likely_owner_files=_unique(owners),
            contract_that_failed="CI command contract",
            noise_to_ignore=(),
            recommended_fix_shape="Open the failed step log around the first nonzero command.",
            verification_commands=("python -m pytest -q <focused-test> -o addopts=",),
            confidence="low",
            next_best_action="capture more log context around the first failed command",
        )

    return CiFailureTriageReport(
        schema_version=SCHEMA_VERSION,
        classification="unknown",
        blocker=False,
        headline_failure="none",
        actual_failure="none",
        root_cause_candidates=(),
        likely_owner_files=_unique(owners),
        contract_that_failed="none",
        noise_to_ignore=(),
        recommended_fix_shape="No actionable CI failure signature was found.",
        verification_commands=(),
        confidence="low",
        next_best_action="provide a failed job log with the failing step output",
    )


def _render_text(report: CiFailureTriageReport) -> str:
    payload = _as_payload(report)
    lines: list[str] = []
    for key, value in payload.items():
        if isinstance(value, bool):
            rendered = "yes" if value else "no"
        elif isinstance(value, (list, tuple)):
            rendered = ", ".join(str(item) for item in value) if value else "none"
        else:
            rendered = str(value)
        lines.append(f"{key}={rendered}")
    return "\n".join(lines) + "\n"


def _render_markdown(report: CiFailureTriageReport) -> str:
    return (
        "# CI failure triage\n\n"
        f"- classification: `{report.classification}`\n"
        f"- blocker: `{'yes' if report.blocker else 'no'}`\n"
        f"- headline failure: {report.headline_failure}\n"
        f"- actual failure: {report.actual_failure}\n"
        f"- contract that failed: {report.contract_that_failed}\n"
        f"- likely owner files: {', '.join(report.likely_owner_files) or 'none'}\n"
        f"- noise to ignore: {', '.join(report.noise_to_ignore) or 'none'}\n"
        f"- recommended fix shape: {report.recommended_fix_shape}\n"
        f"- verification: {', '.join(report.verification_commands) or 'none'}\n"
        f"- confidence: `{report.confidence}`\n"
        f"- next best action: {report.next_best_action}\n"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit triage-ci",
        description="Diagnose failed CI logs and recommend advisory-only verification.",
    )
    parser.add_argument("--log", required=True, help="Path to a saved failed CI job log.")
    parser.add_argument(
        "--format",
        choices=["text", "json", "md", "markdown"],
        default="text",
        help="Output format.",
    )
    parser.add_argument("--output", default="", help="Optional file path to write the report.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    text = Path(args.log).read_text(encoding="utf-8", errors="replace")
    report = build_triage_report(text)

    if args.format == "json":
        rendered = json.dumps(_as_payload(report), indent=2, sort_keys=True) + "\n"
    elif args.format in {"md", "markdown"}:
        rendered = _render_markdown(report)
    else:
        rendered = _render_text(report)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")

    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
