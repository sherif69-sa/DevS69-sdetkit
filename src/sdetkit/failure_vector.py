from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA_VERSION = "sdetkit.failure_vector.v1"
BUNDLE_SCHEMA_VERSION = "sdetkit.failure_vector.bundle.v1"

PYTEST_NODE_RE = re.compile(r"FAILED\s+(?P<node>[^\s]+::[^\s]+)")
PY_FILE_RE = re.compile(r"(?P<path>(?:src|tests)/[A-Za-z0-9_./-]+\.py)")
MYPY_ERROR_RE = re.compile(r"(?P<path>(?:src|tests)/[A-Za-z0-9_./-]+\.py):\d+:\s+error:")
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
    failure_index = _first_failing_line_index(lines)
    first_line = _line_at(lines, failure_index)
    failure_class = _classify_failure(log_text, first_line)
    affected_files = _affected_files(log_text, first_line)

    return FailureVector(
        check=check,
        command=_extract_command(lines, failure_index),
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


def build_failure_vector_bundle(
    log_paths: Sequence[str | Path],
    *,
    environment: str = "unknown",
) -> dict[str, object]:
    vectors = []
    for raw_path in log_paths:
        path = Path(raw_path)
        vector = extract_failure_vector(
            path.read_text(encoding="utf-8", errors="ignore"),
            check=path.parent.name if path.parent.name else path.stem,
            log_url=path.as_posix(),
            environment=environment,
        )
        vectors.append(vector.to_dict())

    by_class = Counter(str(vector["failure_class"]) for vector in vectors)
    by_risk = Counter(str(vector["risk"]) for vector in vectors)

    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "vector_schema_version": SCHEMA_VERSION,
        "environment": environment,
        "failure_vector_count": len(vectors),
        "summary": {
            "by_failure_class": dict(sorted(by_class.items())),
            "by_risk": dict(sorted(by_risk.items())),
            "safe_fix_candidate_count": sum(
                1 for vector in vectors if bool(vector["safe_fix_candidate"])
            ),
            "review_first_count": sum(
                1 for vector in vectors if not bool(vector["safe_fix_candidate"])
            ),
        },
        "failure_vectors": vectors,
    }


def write_failure_vector(vector: FailureVector, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(vector.to_dict(), indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")


def write_failure_vector_bundle(
    log_paths: Sequence[str | Path],
    path: Path,
    *,
    environment: str = "unknown",
) -> dict[str, object]:
    payload = build_failure_vector_bundle(log_paths, environment=environment)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def render_failure_vector_report(vector: FailureVector) -> str:
    from sdetkit.safety_gate import evaluate_failure_vector

    decision = evaluate_failure_vector(vector)
    safe = "yes" if vector.safe_fix_candidate else "no"
    allowed = "yes" if decision.safe_fix_allowed else "no"
    review_first = "yes" if decision.review_first else "no"
    local_repro = vector.local_repro_command or "none"
    first_line = vector.first_failing_line or "unknown"
    affected = ", ".join(vector.affected_files) if vector.affected_files else "none"
    allowed_files = ", ".join(decision.allowed_files) if decision.allowed_files else "none"
    proof_commands = ", ".join(decision.proof_commands) if decision.proof_commands else "none"
    return "\n".join(
        [
            "# Failure Vector",
            "",
            f"- check: `{vector.check}`",
            f"- command: `{vector.command}`",
            f"- class: `{vector.failure_class}`",
            f"- risk: `{vector.risk}`",
            f"- scope: `{vector.scope}`",
            f"- safe_fix_candidate: `{safe}`",
            f"- affected_files: `{affected}`",
            f"- first_failing_line: `{first_line}`",
            f"- local_repro_command: `{local_repro}`",
            "",
            "## SafetyGate Decision",
            "",
            f"- safe_fix_allowed: `{allowed}`",
            f"- review_first: `{review_first}`",
            f"- reason: `{decision.reason}`",
            f"- allowed_files: `{allowed_files}`",
            f"- proof_commands: `{proof_commands}`",
            "- automation_allowed: `false`",
            "- patch_application_allowed: `false`",
            "- merge_authorized: `false`",
            "",
        ]
    )


def render_failure_vector_bundle_report(payload: dict[str, object]) -> str:
    from sdetkit.safety_gate import evaluate_failure_vector

    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value))
        except ValueError:
            return None

    def _optional_string(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _affected_files(value: object) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)):
            return ()
        return tuple(str(item) for item in value if str(item).strip())

    def _vector_from_payload(value: dict[object, object]) -> FailureVector:
        return FailureVector(
            check=str(value.get("check") or "unknown"),
            command=str(value.get("command") or "unknown"),
            exit_code=_optional_int(value.get("exit_code")),
            failure_class=str(value.get("failure_class") or "unknown"),
            risk=str(value.get("risk") or "unknown"),
            scope=str(value.get("scope") or "unknown"),
            reproducible_locally=str(value.get("reproducible_locally") or "not_run"),
            safe_fix_candidate=bool(value.get("safe_fix_candidate", False)),
            first_failing_line=str(value.get("first_failing_line") or ""),
            affected_files=_affected_files(value.get("affected_files")),
            log_url=_optional_string(value.get("log_url")),
            local_repro_command=_optional_string(value.get("local_repro_command")),
            environment=str(value.get("environment") or "unknown"),
            schema_version=str(value.get("schema_version") or SCHEMA_VERSION),
        )

    summary = payload.get("summary", {})
    summary = summary if isinstance(summary, dict) else {}
    by_class = summary.get("by_failure_class", {})
    by_class = by_class if isinstance(by_class, dict) else {}

    raw_vectors = payload.get("failure_vectors", [])
    vector_payloads = (
        [item for item in raw_vectors if isinstance(item, dict)]
        if isinstance(raw_vectors, list)
        else []
    )
    safety_decisions = [
        evaluate_failure_vector(_vector_from_payload(vector_payload))
        for vector_payload in vector_payloads
    ]
    safe_fix_allowed_count = sum(1 for decision in safety_decisions if decision.safe_fix_allowed)
    safety_review_first_count = sum(1 for decision in safety_decisions if decision.review_first)
    safety_allowed_files = sorted(
        {path for decision in safety_decisions for path in decision.allowed_files}
    )
    safety_proof_commands = sorted(
        {command for decision in safety_decisions for command in decision.proof_commands}
    )

    lines = [
        "# Failure Vector Bundle",
        "",
        f"- schema_version: `{payload.get('schema_version', 'unknown')}`",
        f"- failure_vector_count: `{payload.get('failure_vector_count', 0)}`",
        f"- safe_fix_candidate_count: `{summary.get('safe_fix_candidate_count', 0)}`",
        f"- review_first_count: `{summary.get('review_first_count', 0)}`",
        "",
        "## SafetyGate summary",
        "",
        f"- safe_fix_allowed_count: `{safe_fix_allowed_count}`",
        f"- safety_review_first_count: `{safety_review_first_count}`",
        "- safety_allowed_files: "
        + (
            ", ".join(f"`{path}`" for path in safety_allowed_files)
            if safety_allowed_files
            else "`none`"
        ),
        "- safety_proof_commands: "
        + (
            ", ".join(f"`{command}`" for command in safety_proof_commands)
            if safety_proof_commands
            else "`none`"
        ),
        "- automation_allowed: `false`",
        "- patch_application_allowed: `false`",
        "- merge_authorized: `false`",
        "",
        "## By failure class",
        "",
    ]

    if by_class:
        lines.extend(f"- `{name}`: `{count}`" for name, count in sorted(by_class.items()))
    else:
        lines.append("- none")

    lines.append("")
    return "\n".join(lines)


def _line_at(lines: Sequence[str], index: int) -> str:
    if index < 0 or index >= len(lines):
        return ""
    return lines[index].strip()


def _first_failing_line(lines: list[str]) -> str:
    return _line_at(lines, _first_failing_line_index(lines))


def _first_failing_line_index(lines: Sequence[str]) -> int:
    generic_index = -1

    for index, line in enumerate(lines):
        stripped = line.strip()
        lowered = stripped.lower()

        if not stripped:
            continue

        if stripped.startswith("FAILED "):
            return index
        if MYPY_ERROR_RE.search(stripped):
            return index
        if "would be reformatted" in lowered:
            return index
        if "ruff format" in lowered and "failed" in lowered:
            return index
        if RUFF_RULE_RE.search(stripped) and "-->" in "\n".join(lines[index : index + 4]):
            return index
        if stripped.startswith(("ERROR ", "ERROR:")):
            return index
        if stripped.startswith("Traceback"):
            return index
        if "merge conflict" in lowered or stripped.startswith("CONFLICT "):
            return index
        if "npm err!" in lowered:
            return index
        if "process completed with exit code" in lowered:
            generic_index = index

    return generic_index


def _extract_command(lines: Sequence[str], failure_index: int) -> str:
    upper_bound = failure_index if failure_index >= 0 else len(lines)

    for line in reversed(lines[:upper_bound]):
        stripped = line.strip()

        if stripped.startswith("Run "):
            return stripped.removeprefix("Run ").strip()
        if "##[group]Run " in stripped:
            return stripped.split("Run ", 1)[1].strip()
        if stripped.startswith("$ "):
            return stripped[2:].strip()
        if "python -m " in stripped or "pytest" in stripped or "mypy" in stripped:
            return stripped

    return "unknown"


def _classify_failure(log_text: str, first_line: str) -> str:
    lowered = f"{first_line}\n{log_text}".lower()
    if "ruff format" in lowered or "would reformat" in lowered or "would be reformatted" in lowered:
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
