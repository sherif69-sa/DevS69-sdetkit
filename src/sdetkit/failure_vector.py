from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA_VERSION = "sdetkit.failure_vector.v1"

PYTEST_NODE_RE = re.compile(r"FAILED\s+(?P<node>[^\s]+::[^\s]+)")
PY_FILE_RE = re.compile(r"(?P<path>(?:src|tests)/[A-Za-z0-9_./-]+\.py)")
RUFF_RULE_RE = re.compile(r"\b(?P<rule>[A-Z]\d{3})\b")
EXIT_CODE_RE = re.compile(r"Process completed with exit code (?P<code>\d+)")


@dataclass(frozen=True)
class FailureVector:
    check: str
    command: str
    exit_code: int | None
    failure_class: str
    risk: str
    scope: str
    reproducible_locally: str
    safe_fix_candidate: bool
    first_failing_line: str
    affected_files: tuple[str, ...]
    log_url: str | None
    local_repro_command: str | None
    environment: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["affected_files"] = list(self.affected_files)
        return payload


def extract_failure_vector(
    log_text: str,
    *,
    check: str = "unknown",
    log_url: str | None = None,
    environment: str = "unknown",
) -> FailureVector:
    lines = [line.rstrip() for line in log_text.splitlines()]
    first_line = _first_failing_line(lines)
    failure_class = _classify_failure(log_text, first_line)
    affected_files = _affected_files(log_text, first_line)

    return FailureVector(
        check=check,
        command="unknown",
        exit_code=_extract_exit_code(log_text),
        failure_class=failure_class,
        risk=_risk_for_class(failure_class),
        scope=_scope_for_files(affected_files),
        reproducible_locally="not_run",
        safe_fix_candidate=_safe_fix_candidate(failure_class, first_line),
        first_failing_line=first_line,
        affected_files=affected_files,
        log_url=log_url,
        local_repro_command=_local_repro_command(failure_class, affected_files, first_line),
        environment=environment,
    )


def write_failure_vector(vector: FailureVector, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(vector.to_dict(), indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")


def render_failure_vector_report(vector: FailureVector) -> str:
    safe = "yes" if vector.safe_fix_candidate else "no"
    local_repro = vector.local_repro_command or "none"
    first_line = vector.first_failing_line or "unknown"
    return "\n".join(
        [
            "# Failure Vector",
            "",
            f"- check: `{vector.check}`",
            f"- class: `{vector.failure_class}`",
            f"- risk: `{vector.risk}`",
            f"- safe_fix_candidate: `{safe}`",
            f"- first_failing_line: `{first_line}`",
            f"- local_repro_command: `{local_repro}`",
            "",
        ]
    )


def _first_failing_line(lines: list[str]) -> str:
    needles = (
        "FAILED ",
        "ERROR ",
        "AssertionError",
        "Traceback",
        "ruff format",
        "ruff check",
        "mypy",
        "Merge conflict",
        "CONFLICT ",
        "npm ERR!",
        "Process completed with exit code",
    )
    for line in lines:
        stripped = line.strip()
        if stripped and any(needle in stripped for needle in needles):
            return stripped
    return ""


def _classify_failure(log_text: str, first_line: str) -> str:
    lowered = f"{first_line}\n{log_text}".lower()
    if "ruff format" in lowered or "would reformat" in lowered:
        return "formatter_only"
    if "ruff check" in lowered or RUFF_RULE_RE.search(first_line):
        return "lint"
    if "mypy" in lowered and "error:" in lowered:
        return "type"
    if first_line.startswith("FAILED ") or "assertionerror" in lowered or "pytest" in lowered:
        return "test"
    if "npm err!" in lowered or "dependency conflict" in lowered:
        return "dependency"
    if "conflict " in lowered or "merge conflict" in lowered:
        return "merge_conflict"
    if "timed out" in lowered or "connection reset" in lowered:
        return "infra"
    if "twine" in lowered or "wheel" in lowered or "release" in lowered:
        return "release"
    if "secret" in lowered or "codeql" in lowered or "vulnerability" in lowered:
        return "security"
    return "unknown"


def _affected_files(log_text: str, first_line: str) -> tuple[str, ...]:
    found: list[str] = []
    for source in (first_line, log_text):
        for match in PY_FILE_RE.finditer(source):
            path = match.group("path")
            if path not in found:
                found.append(path)
    return tuple(found)


def _extract_exit_code(log_text: str) -> int | None:
    match = EXIT_CODE_RE.search(log_text)
    return int(match.group("code")) if match else None


def _risk_for_class(failure_class: str) -> str:
    if failure_class in {"security", "release", "dependency", "merge_conflict", "unknown"}:
        return "high"
    if failure_class in {"test", "type", "infra"}:
        return "medium"
    return "low"


def _scope_for_files(files: tuple[str, ...]) -> str:
    if not files:
        return "unknown"
    if all(path.startswith(("src/", "tests/")) for path in files):
        return "pr_owned_only"
    return "repo_wide"


def _safe_fix_candidate(failure_class: str, first_line: str) -> bool:
    if failure_class == "formatter_only":
        return True
    if failure_class == "lint":
        rule_match = RUFF_RULE_RE.search(first_line)
        return bool(rule_match and rule_match.group("rule") == "I001")
    return False


def _local_repro_command(
    failure_class: str,
    affected_files: tuple[str, ...],
    first_line: str,
) -> str | None:
    pytest_match = PYTEST_NODE_RE.search(first_line)
    if pytest_match:
        node = pytest_match.group("node")
        return f"PYTHONPATH=src python -m pytest -q {node} -o addopts="
    if failure_class == "formatter_only" and affected_files:
        return "python -m ruff format --check " + " ".join(affected_files)
    if failure_class == "lint" and affected_files:
        return "python -m ruff check " + " ".join(affected_files)
    if failure_class == "type":
        return "python -m mypy src"
    return None
