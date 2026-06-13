from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA_VERSION = "sdetkit.failure_vector.v1"
CONTRACT_SCHEMA_VERSION = "sdetkit.failure_vector.contract.v1"
BUNDLE_SCHEMA_VERSION = "sdetkit.failure_vector.bundle.v1"

PYTEST_NODE_RE = re.compile(r"FAILED\s+(?P<node>[^\s]+::[^\s]+)")
PY_FILE_RE = re.compile(r"(?P<path>(?:src|tests)/[A-Za-z0-9_./-]+\.py)")
MYPY_ERROR_RE = re.compile(r"(?P<path>(?:src|tests)/[A-Za-z0-9_./-]+\.py):\d+:\s+error:")
RUFF_RULE_RE = re.compile(r"\b(?P<rule>[A-Z]\d{3})\b")
EXIT_CODE_RE = re.compile(r"Process completed with exit code (?P<code>\d+)")
PYTEST_NODE_ANY_RE = re.compile(r"(?P<node>(?:src|tests)/[A-Za-z0-9_./-]+\.py::[^\s]+)")
PRECOMMIT_HOOK_RE = re.compile(r"^(?P<hook>.+?)\.+Failed$")


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
    headline_signal: str = ""
    actual_failure: str = ""
    failure_type: str = ""
    failing_command: str = ""
    failing_test_or_check: str = ""
    owner_hint: str = ""
    safe_fix_allowed: bool = False
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["affected_files"] = list(self.affected_files)
        payload["contract"] = failure_vector_contract(self)
        return payload


def failure_vector_contract(vector: FailureVector) -> dict[str, object]:
    failure_kind = vector.failure_type or vector.failure_class or "unknown"
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "failure_kind": failure_kind,
        "affected_surface": _contract_affected_surface(vector.affected_files),
        "ownership_area": _contract_ownership_area(vector),
        "retryability": _contract_retryability(failure_kind),
        "security_relevance": failure_kind == "security",
        "recommended_next_human_action": _contract_next_action(vector, failure_kind),
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_claim": False,
    }


def _contract_affected_surface(affected_files: tuple[str, ...]) -> str:
    if not affected_files:
        return "unknown"
    if all(path.startswith("tests/") for path in affected_files):
        return "tests"
    if all(path.startswith("src/") for path in affected_files):
        return "source"
    if all(path.startswith(("src/", "tests/")) for path in affected_files):
        return "code"
    return "repo_wide"


def _contract_ownership_area(vector: FailureVector) -> str:
    if vector.owner_hint and vector.owner_hint != "unknown":
        return vector.owner_hint
    if vector.affected_files:
        return vector.affected_files[0]
    return vector.check or "unknown"


def _contract_retryability(failure_kind: str) -> str:
    if failure_kind in {"dependency", "merge_conflict", "release", "security", "unknown"}:
        return "human_review_required"
    return "not_retryable_without_change"


def _contract_next_action(vector: FailureVector, failure_kind: str) -> str:
    if failure_kind == "security":
        return "perform security review; do not dismiss automatically"
    if failure_kind == "merge_conflict":
        return "resolve conflicts manually and rerun full proof"
    if failure_kind == "dependency":
        return "review dependency constraints and resolver output before changing locks"
    if failure_kind == "test":
        return "inspect failing test and affected file before patching"
    if vector.safe_fix_candidate:
        return "review generated fix and run proof commands"
    return "triage failure and rerun focused proof"


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
    actual_failure = _actual_failure_line(lines, failure_index, first_line)
    failure_class = _classify_failure(log_text, first_line)
    affected_files = _affected_files(log_text, actual_failure or first_line)
    command = _extract_command(lines, failure_index)
    safe_candidate = _safe_fix_candidate(failure_class, actual_failure or first_line)

    return FailureVector(
        check=check,
        command=command,
        exit_code=_extract_exit_code(log_text),
        failure_class=failure_class,
        risk=_risk_for_class(
            failure_class,
            safe_fix_candidate=safe_candidate,
        ),
        scope=_scope_for_files(affected_files),
        reproducible_locally="not_run",
        safe_fix_candidate=safe_candidate,
        first_failing_line=first_line,
        affected_files=affected_files,
        log_url=log_url,
        local_repro_command=_local_repro_command(
            failure_class,
            affected_files,
            actual_failure or first_line,
        ),
        environment=environment,
        headline_signal=_headline_signal(check, failure_class, first_line),
        actual_failure=actual_failure or first_line,
        failure_type=failure_class,
        failing_command=command,
        failing_test_or_check=_failing_test_or_check(check, first_line, actual_failure),
        owner_hint=_owner_hint(affected_files, check),
        safe_fix_allowed=False,
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
    contract = failure_vector_contract(vector)
    safe = "yes" if vector.safe_fix_candidate else "no"
    allowed = "yes" if decision.safe_fix_allowed else "no"
    review_first = "yes" if decision.review_first else "no"
    local_repro = vector.local_repro_command or "none"
    first_line = vector.first_failing_line or "unknown"
    actual_failure = vector.actual_failure or first_line
    headline_signal = vector.headline_signal or "unknown"
    failing_command = vector.failing_command or vector.command or "unknown"
    failing_test_or_check = vector.failing_test_or_check or vector.check or "unknown"
    owner_hint = vector.owner_hint or "unknown"
    explicit_safe_fix_allowed = "yes" if vector.safe_fix_allowed else "no"
    affected = ", ".join(vector.affected_files) if vector.affected_files else "none"
    allowed_files = ", ".join(decision.allowed_files) if decision.allowed_files else "none"
    proof_commands = ", ".join(decision.proof_commands) if decision.proof_commands else "none"
    return "\n".join(
        [
            "# Failure Vector",
            "",
            f"- check: `{vector.check}`",
            f"- command: `{vector.command}`",
            f"- headline_signal: `{headline_signal}`",
            f"- actual_failure: `{actual_failure}`",
            f"- failure_type: `{vector.failure_type or vector.failure_class}`",
            f"- failing_command: `{failing_command}`",
            f"- failing_test_or_check: `{failing_test_or_check}`",
            f"- owner_hint: `{owner_hint}`",
            f"- class: `{vector.failure_class}`",
            f"- risk: `{vector.risk}`",
            f"- scope: `{vector.scope}`",
            f"- safe_fix_candidate: `{safe}`",
            f"- safe_fix_allowed: `{explicit_safe_fix_allowed}`",
            f"- affected_files: `{affected}`",
            f"- first_failing_line: `{first_line}`",
            f"- local_repro_command: `{local_repro}`",
            "",
            "## Normalized Failure Vector Contract",
            "",
            f"- contract_schema_version: `{contract['schema_version']}`",
            f"- failure_kind: `{contract['failure_kind']}`",
            f"- affected_surface: `{contract['affected_surface']}`",
            f"- ownership_area: `{contract['ownership_area']}`",
            f"- retryability: `{contract['retryability']}`",
            f"- security_relevance: `{str(contract['security_relevance']).lower()}`",
            f"- recommended_next_human_action: `{contract['recommended_next_human_action']}`",
            f"- reporting_only: `{str(contract['reporting_only']).lower()}`",
            f"- automation_allowed: `{str(contract['automation_allowed']).lower()}`",
            f"- patch_application_allowed: `{str(contract['patch_application_allowed']).lower()}`",
            "- security_dismissal_allowed: "
            f"`{str(contract['security_dismissal_allowed']).lower()}`",
            f"- merge_authorized: `{str(contract['merge_authorized']).lower()}`",
            "- semantic_equivalence_claim: "
            f"`{str(contract['semantic_equivalence_claim']).lower()}`",
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
            headline_signal=str(value.get("headline_signal") or ""),
            actual_failure=str(value.get("actual_failure") or ""),
            failure_type=str(value.get("failure_type") or ""),
            failing_command=str(value.get("failing_command") or ""),
            failing_test_or_check=str(value.get("failing_test_or_check") or ""),
            owner_hint=str(value.get("owner_hint") or ""),
            safe_fix_allowed=bool(value.get("safe_fix_allowed", False)),
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
        "## Failure vectors",
        "",
    ]

    if vector_payloads:
        for vector_payload in sorted(
            vector_payloads,
            key=lambda item: str(item.get("check") or "unknown"),
        ):
            affected_files = _affected_files(vector_payload.get("affected_files"))
            affected = ", ".join(f"`{path}`" for path in affected_files) or "`none`"
            safe = "yes" if bool(vector_payload.get("safe_fix_candidate", False)) else "no"
            local_repro = _optional_string(vector_payload.get("local_repro_command")) or "none"
            lines.extend(
                [
                    f"### {str(vector_payload.get('check') or 'unknown')}",
                    "",
                    f"- headline_signal: `{str(vector_payload.get('headline_signal') or 'unknown')}`",
                    f"- actual_failure: `{str(vector_payload.get('actual_failure') or vector_payload.get('first_failing_line') or 'unknown')}`",
                    f"- failure_type: `{str(vector_payload.get('failure_type') or vector_payload.get('failure_class') or 'unknown')}`",
                    f"- failing_command: `{str(vector_payload.get('failing_command') or vector_payload.get('command') or 'unknown')}`",
                    f"- failing_test_or_check: `{str(vector_payload.get('failing_test_or_check') or vector_payload.get('check') or 'unknown')}`",
                    f"- owner_hint: `{str(vector_payload.get('owner_hint') or 'unknown')}`",
                    f"- class: `{str(vector_payload.get('failure_class') or 'unknown')}`",
                    f"- risk: `{str(vector_payload.get('risk') or 'unknown')}`",
                    f"- safe_fix_candidate: `{safe}`",
                    f"- safe_fix_allowed: `{'yes' if bool(vector_payload.get('safe_fix_allowed', False)) else 'no'}`",
                    f"- first_failing_line: `{str(vector_payload.get('first_failing_line') or 'unknown')}`",
                    f"- affected_files: {affected}",
                    f"- local_repro_command: `{local_repro}`",
                    "",
                ]
            )
    else:
        lines.append("- none")
        lines.append("")

    lines.extend(["## By failure class", ""])

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
    fallback_index = -1
    generic_exit_index = -1

    for index, line in enumerate(lines):
        stripped = line.strip()
        lower = stripped.lower()

        if not stripped:
            continue

        if "process completed with exit code" in lower:
            if generic_exit_index < 0:
                generic_exit_index = index
            continue

        if stripped.startswith("Run ") or stripped.startswith("$ "):
            continue

        if stripped.startswith("FAILED "):
            return index
        if MYPY_ERROR_RE.search(stripped):
            return index
        if "ruff format" in lower and "failed" in lower:
            return index
        if "would be reformatted" in lower:
            return index
        if (
            "resolutionimpossible" in lower
            or "no matching distribution found" in lower
            or "could not find a version that satisfies" in lower
            or "pip's dependency resolver" in lower
        ):
            return index
        if "merge conflict" in lower or stripped.startswith("CONFLICT "):
            return index
        if stripped.startswith("ERROR ") or stripped.startswith("ERROR:"):
            if fallback_index < 0:
                fallback_index = index
            continue

        if fallback_index < 0:
            fallback_index = index

    if fallback_index >= 0:
        return fallback_index
    if generic_exit_index >= 0:
        return generic_exit_index
    return 0


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
    haystack = f"{first_line}\n{log_text}".lower()

    if "merge conflict" in haystack or "<<<<<<<" in haystack or "conflict " in haystack:
        return "merge_conflict"

    if (
        "resolutionimpossible" in haystack
        or "no matching distribution found" in haystack
        or "could not find a version that satisfies" in haystack
        or "pip's dependency resolver" in haystack
    ):
        return "dependency"

    if "ruff format" in haystack or "would be reformatted" in haystack:
        return "formatter_only"

    if RUFF_RULE_RE.search(first_line) or (
        "ruff check" in haystack and ("-->" in haystack or RUFF_RULE_RE.search(log_text))
    ):
        return "lint"

    if "ruff" in haystack and ("failed" in haystack or "error" in haystack):
        return "lint"

    if "mypy" in haystack or MYPY_ERROR_RE.search(first_line):
        return "type"

    if (
        first_line.strip().startswith("FAILED ")
        or "pytest" in haystack
        or "assertionerror" in haystack
    ):
        return "test"

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


def _actual_failure_line(lines: Sequence[str], failure_index: int, first_line: str) -> str:
    start = failure_index if failure_index >= 0 else 0
    search_window = list(lines[start : start + 40])

    for raw_line in search_window:
        stripped = raw_line.strip()
        lower = stripped.lower()

        if not stripped or _failure_line_is_noise(stripped):
            continue
        if (
            stripped.startswith("FAILED ")
            or MYPY_ERROR_RE.search(stripped)
            or RUFF_RULE_RE.search(stripped)
            or "assertionerror" in lower
            or "modulenotfounderror" in lower
            or "importerror" in lower
            or "resolutionimpossible" in lower
            or "no matching distribution found" in lower
            or "could not find a version that satisfies" in lower
            or "would be reformatted" in lower
            or stripped.startswith("ERROR ")
            or stripped.startswith("ERROR:")
        ):
            return stripped

    if first_line and not _failure_line_is_noise(first_line):
        return first_line

    for raw_line in search_window:
        stripped = raw_line.strip()
        if stripped and not _failure_line_is_noise(stripped):
            return stripped

    return first_line


def _failure_line_is_noise(line: str) -> bool:
    lower = line.lower()

    if "process completed with exit code" in lower:
        return True
    if line.startswith("Run ") or line.startswith("$ ") or "##[group]Run " in line:
        return True
    if PRECOMMIT_HOOK_RE.match(line) and not RUFF_RULE_RE.search(line):
        return True

    return False


def _headline_signal(check: str, failure_class: str, first_line: str) -> str:
    check_text = check.strip() or "unknown"
    if first_line:
        return f"{check_text}: {failure_class}"
    return f"{check_text}: no failure signal"


def _failing_test_or_check(check: str, first_line: str, actual_failure: str) -> str:
    for source in (first_line, actual_failure):
        pytest_match = PYTEST_NODE_RE.search(source) or PYTEST_NODE_ANY_RE.search(source)
        if pytest_match:
            return pytest_match.group("node")

        mypy_match = MYPY_ERROR_RE.search(source)
        if mypy_match:
            return mypy_match.group("path")

        rule_match = RUFF_RULE_RE.search(source)
        if rule_match:
            return rule_match.group("rule")

    return check.strip() or "unknown"


def _owner_hint(affected_files: tuple[str, ...], check: str) -> str:
    if affected_files:
        return affected_files[0]
    return check.strip() or "unknown"


def _risk_for_class(failure_class: str, *, safe_fix_candidate: bool = False) -> str:
    if safe_fix_candidate and failure_class in {"formatter_only", "lint"}:
        return "low"

    return {
        "formatter_only": "low",
        "lint": "medium",
        "test": "medium",
        "type": "medium",
        "dependency": "high",
        "merge_conflict": "high",
        "release": "high",
        "security": "high",
        "unknown": "high",
    }.get(failure_class, "high")


def _scope_for_files(files: tuple[str, ...]) -> str:
    if not files:
        return "unknown"
    if all(path.startswith(("src/", "tests/")) for path in files):
        return "pr_owned_only"
    return "repo_wide"


def _safe_fix_candidate(failure_class: str, first_line: str) -> bool:
    if failure_class == "formatter_only":
        return True

    stripped = first_line.strip()
    if failure_class == "lint" and stripped.startswith("I001") and "[*]" in stripped:
        return True

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
