from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from sdetkit import safe_remediation_eligibility

from . import adaptive_diagnosis

CHECK_INTELLIGENCE_SCHEMA_VERSION = "sdetkit.pr_quality.check_intelligence.v1"
ACTION_REPORT_SCHEMA_VERSION = "sdetkit.pr_quality.action_report.v1"

JsonObject = dict[str, Any]

DEPENDENCY_AUDIT_VULNERABILITY = "DEPENDENCY_AUDIT_VULNERABILITY"
CODE_SCANNING_CURRENT_ALERT = "_".join(("CODE", "SCANNING", "CURRENT", "ALERT"))
DEPENDENCY_AUDIT_OWNER_FILES = [
    "requirements-test.txt",
    "requirements-docs.txt",
    "requirements.txt",
    "constraints-ci.txt",
    "pyproject.toml",
    ".github/workflows/",
    ".github/scripts/check_pip_audit_baseline.py",
]


def _extract_dependency_audit_evidence(log_text: str) -> JsonObject:

    command = ""
    report_path = ""
    artifact_url = ""
    ignored: list[str] = []
    vulnerability_count = 0
    package_count = 0

    for raw_line in log_text.splitlines():
        line = raw_line.strip()
        if "pip-audit " in line and not command:
            command = line
            ignored = re.findall(r"--ignore-vuln\s+([A-Za-z0-9_.:-]+)", line)
            report_match = re.search(r"(?:-o|--output)\s+(\S+)", line)
            if report_match:
                report_path = report_match.group(1)

        if "path:" in line and "pip-audit-report" in line and not report_path:
            report_path = line.split("path:", 1)[1].strip()

        if "Artifact download URL:" in line and "artifact" in line.lower():
            artifact_url = line.split("Artifact download URL:", 1)[1].strip()

        summary_match = re.search(
            r"Found\s+(\d+)\s+known\s+vulnerabilit(?:y|ies)\s+in\s+(\d+)\s+package",
            line,
            flags=re.IGNORECASE,
        )
        if summary_match:
            vulnerability_count = int(summary_match.group(1))
            package_count = int(summary_match.group(2))

    if not vulnerability_count:
        return {}

    return {
        "vulnerability_count": vulnerability_count,
        "package_count": package_count,
        "command": command,
        "report_path": report_path,
        "artifact_url": artifact_url,
        "ignored_vulnerabilities": ignored,
    }


_FAILURE_CONCLUSIONS = {
    "action_required",
    "cancelled",
    "failure",
    "startup_failure",
    "timed_out",
}

_SUCCESS_CONCLUSIONS = {
    "neutral",
    "skipped",
    "success",
}

_PENDING_STATUSES = {
    "expected",
    "in_progress",
    "pending",
    "queued",
    "requested",
    "waiting",
}

_SAFE_AUTO_FIX_CODES = {
    "PRE_COMMIT_FORMAT_DRIFT",
    "RUFF_FIXABLE_LINT",
}

_DIAGNOSIS_SURFACES = {
    "PACKAGE_INSTALL_FAILURE": "dependency",
    "MISSING_TEST_DEPENDENCY": "dependency",
    "SECURITY_FINDING_REVIEW_REQUIRED": "security",
    "SECRET_EXPOSURE": "security",
    "RELEASE_ARTIFACT_INVALID": "release",
    "WORKFLOW_CONTRACT_FAILURE": "workflow",
    "CLI_CONTRACT_FAILURE": "cli",
    "PYTHON_RUNTIME_EXCEPTION": "workflow",
    "DOCS_BUILD_CONTRACT": "docs",
    "PYTEST_ASSERTION_FAILURE": "tests",
    "PYTEST_IMPORT_FAILURE": "tests",
    "PRE_COMMIT_FORMAT_DRIFT": "quality",
    "RUFF_FIXABLE_LINT": "quality",
    "RUFF_LINT_FAILURE": "quality",
    "MYPY_TYPE_CONTRACT_DRIFT": "quality",
    "COVERAGE_GATE_REGRESSION": "quality",
    "CODEQL_SECURITY_REVIEW_REQUIRED": "security",
    "VALIDATE_JOB_LOG_REVIEW": "workflow",
}


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _as_dict(payload)


def _write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "check"


def _iter_check_records(payload: JsonObject) -> list[JsonObject]:
    if isinstance(payload.get("checks"), list):
        return [_as_dict(item) for item in _as_list(payload.get("checks"))]

    records: list[JsonObject] = []
    for key in (
        "check_runs",
        "jobs",
        "workflow_runs",
        "statuses",
        "check_suites",
    ):
        records.extend(_as_dict(item) for item in _as_list(payload.get(key)))

    if not records and payload:
        records.append(payload)

    return records


def _check_name(record: JsonObject, index: int) -> str:
    for key in ("name", "displayName", "workflowName", "context", "check_name"):
        value = _string(record.get(key))
        if value:
            return value
    return f"check-{index + 1}"


def _check_status(record: JsonObject) -> str:
    return _string(record.get("status")).lower()


def _check_conclusion(record: JsonObject) -> str:
    return _string(record.get("conclusion") or record.get("state")).lower()


def _is_failed(record: JsonObject) -> bool:
    conclusion = _check_conclusion(record)
    status = _check_status(record)
    if conclusion in _FAILURE_CONCLUSIONS:
        return True
    return status == "completed" and conclusion not in _SUCCESS_CONCLUSIONS


def _is_queued_or_pending(record: JsonObject) -> bool:
    status = _check_status(record)
    conclusion = _check_conclusion(record)
    return status in _PENDING_STATUSES and conclusion not in _FAILURE_CONCLUSIONS


def _is_cancelled(record: JsonObject) -> bool:
    return _check_conclusion(record) == "cancelled"


def _is_startup_failure(record: JsonObject) -> bool:
    return _check_conclusion(record) == "startup_failure"


def _check_required(record: JsonObject) -> bool:
    value = record.get("required")
    if isinstance(value, bool):
        return value

    value = record.get("is_required")
    if isinstance(value, bool):
        return value

    value = record.get("required_status")
    if isinstance(value, bool):
        return value

    return False


def _record_url(record: JsonObject) -> str:
    for key in ("url", "html_url", "details_url"):
        value = _string(record.get(key))
        if value:
            return value
    return ""


def _record_log_text(record: JsonObject, logs_dir: Path | None, name: str) -> str:
    for key in ("log", "logs", "stdout", "stderr", "output", "text"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value

    log_path_value = _string(record.get("log_path") or record.get("logPath"))
    if log_path_value:
        log_path = Path(log_path_value)
        if log_path.exists():
            return log_path.read_text(encoding="utf-8", errors="ignore")

    if logs_dir is None or not logs_dir.exists():
        return ""

    slug = _slug(name)
    exact_candidates = [
        logs_dir / f"{slug}.log",
        logs_dir / f"{slug}.txt",
        logs_dir / f"{name}.log",
        logs_dir / f"{name}.txt",
    ]
    for candidate in exact_candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="ignore")

    readable_files = [
        candidate
        for candidate in sorted(logs_dir.rglob("*"))
        if candidate.is_file() and candidate.suffix.lower() in {".log", ".txt"}
    ]
    for candidate in readable_files:
        candidate_slug = _slug(candidate.stem)
        collector_slug = re.sub(r"^[0-9]+-", "", candidate_slug)
        if candidate_slug == slug or collector_slug == slug:
            return candidate.read_text(encoding="utf-8", errors="ignore")

    return ""


def _failure_focused_log_text(text: str, *, context: int = 10, limit: int = 240) -> str:
    lines = text.splitlines()
    if not lines:
        return text

    selected: set[int] = set()
    for index, line in enumerate(lines):
        lowered = line.lower()
        if any(pattern in lowered for pattern in _FAILURE_LINE_PATTERNS):
            start = max(0, index - context)
            end = min(len(lines), index + context + 1)
            selected.update(range(start, end))

    if not selected:
        return "\n".join(lines[-limit:])

    ordered = sorted(selected)
    if len(ordered) > limit:
        ordered = ordered[: limit // 2] + ordered[-(limit // 2) :]

    return "\n".join(lines[index] for index in ordered)


_EXACT_FAILURE_PATTERNS = (
    "files were modified by this hook",
    "would reformat",
    "failed",
    "failure",
    "error:",
    "error ",
    "runtimeerror",
    "traceback",
    "assertionerror",
    "modulenotfounderror",
    "importerror",
    "process completed with exit code",
    "known vulnerability",
    "no tests ran",
    "found 1 error",
    "found ",
    "ruff",
    "mypy",
    "pytest",
)


_FAILURE_LINE_PATTERNS = _EXACT_FAILURE_PATTERNS


_SETUP_NOISE_PREFIXES = (
    "shell:",
    "env:",
    "pythonlocation",
    "python_root_dir",
    "python2_root_dir",
    "python3_root_dir",
    "pkg_config_path",
    "ld_library_path",
    "github_token",
)

_SETUP_NOISE_CONTAINS = (
    "pytest_addopts:",
    "##[group]",
    "##[endgroup]",
    "using cached ",
    "collecting ",
    "downloading ",
    "installing ",
    "installing collected packages",
    "successfully installed",
    "requirement already satisfied",
    "preparing metadata",
    "building wheel",
    "stored in directory",
    "resolved ",
    "looking in indexes",
)


def _is_setup_noise_line(line: str) -> bool:
    lowered = line.strip().lower()
    if not lowered:
        return True
    if "cache not found for input keys:" in lowered:
        return True
    if "cache entry deserialization failed" in lowered:
        return True
    if "python -m pytest" in lowered and not any(
        token in lowered for token in ("failed", "failure", "error", "traceback", "assertion")
    ):
        return True
    return lowered.startswith(_SETUP_NOISE_PREFIXES) or any(
        token in lowered for token in _SETUP_NOISE_CONTAINS
    )


def _record_head_sha(record: JsonObject) -> str:
    for key in ("headSha", "head_sha", "headRefOid", "head_ref_oid", "head_oid"):
        value = _string(record.get(key))
        if value:
            return value

    check_suite = _as_dict(record.get("check_suite") or record.get("checkSuite"))
    for key in ("head_sha", "headSha"):
        value = _string(check_suite.get(key))
        if value:
            return value

    return ""


def _record_current_pr_head_sha(record: JsonObject) -> str:
    for key in ("current_pr_head_sha", "pr_head_sha", "currentHeadSha", "current_head_sha"):
        value = _string(record.get(key))
        if value:
            return value

    pull_request = _as_dict(record.get("pull_request") or record.get("pullRequest"))
    head = _as_dict(pull_request.get("head"))
    return _string(head.get("sha"))


def _check_head_sha(check: JsonObject) -> str:
    return _string(check.get("head_sha") or check.get("headSha"))


def _check_current_pr_head_sha(check: JsonObject, fallback: str = "") -> str:
    return _string(
        check.get("current_pr_head_sha")
        or check.get("pr_head_sha")
        or check.get("currentHeadSha")
        or fallback
    )


def _is_stale_check_evidence(check: JsonObject, *, current_pr_head_sha: str = "") -> bool:
    if bool(check.get("stale_evidence") or check.get("stale")):
        return True

    head_sha = _check_head_sha(check)
    expected_sha = _check_current_pr_head_sha(check, current_pr_head_sha)
    return bool(head_sha and expected_sha and head_sha != expected_sha)


def _path_like_tokens(text: str) -> list[str]:
    import re as _re

    paths = []
    for raw in _re.findall(r"(?:src|tests|tools|docs|templates|\.github)/[A-Za-z0-9_./-]+", text):
        token = raw.strip("`'\"()[]{}:,;")
        if token:
            paths.append(token)
    return sorted(set(paths))


def _formatter_changed_files(log_text: str) -> list[str]:
    files: list[str] = []
    for line in log_text.splitlines():
        lowered = line.lower()
        if (
            "would reformat" in lowered
            or "reformatted" in lowered
            or "files were modified by this hook" in lowered
        ):
            files.extend(_path_like_tokens(line))

    if files:
        return sorted(set(files))

    if "ruff format" not in log_text.lower() and "pre-commit" not in log_text.lower():
        return []

    return _path_like_tokens(log_text)


def _referenced_failure_files(log_text: str) -> list[str]:
    return _path_like_tokens(log_text)


def _changed_files_from_record(record: JsonObject) -> list[str]:
    files: list[str] = []
    for key in (
        "changed_files",
        "pr_changed_files",
        "affected_files",
        "owner_files",
        "files",
    ):
        for item in _as_list(record.get(key)):
            value = _string(item)
            if value:
                files.append(value)
    return sorted(set(files))


def _outside_changed_files(record: JsonObject, log_text: str) -> list[str]:
    changed = set(_changed_files_from_record(record))
    if not changed:
        return []

    referenced = set(_referenced_failure_files(log_text))
    return sorted(path for path in referenced if path not in changed)


def _possible_changed_files_gate_fallout(record: JsonObject, log_text: str) -> bool:
    lowered = log_text.lower()
    outside = _outside_changed_files(record, log_text)
    if outside:
        return True
    return "fatal: bad object" in lowered and "templates/platform_problem" in lowered


def _failure_tool_for_line(line: str) -> str:
    lowered = line.lower()
    if "github check annotation" in lowered:
        return "github_checks"
    if "known vulnerabilit" in lowered and "package" in lowered:
        return "pip-audit"
    if "ruff" in lowered:
        return "ruff"
    if "mypy" in lowered or "type" in lowered:
        return "mypy"
    if "pytest" in lowered or "failed" in lowered or "assertionerror" in lowered:
        return "pytest"
    if "pre-commit" in lowered or "hook" in lowered:
        return "pre_commit"
    if "pip" in lowered or "resolutionimpossible" in lowered or "cannot install" in lowered:
        return "dependency"
    if "traceback" in lowered or "runtimeerror" in lowered:
        return "python"
    return "unknown"


def _failure_kind_for_line(line: str) -> str:
    lowered = line.lower()
    if "github check annotation" in lowered:
        return "check_run_annotation"
    if "known vulnerabilit" in lowered and "package" in lowered:
        return "dependency_vulnerability"
    if (
        "ruff format" in lowered
        or "ruff-format" in lowered
        or "files were modified by this hook" in lowered
        or "would reformat" in lowered
    ):
        return "format_drift"
    if "mypy" in lowered or "type" in lowered or ": error:" in lowered:
        return "type_contract"
    if "assertionerror" in lowered or "pytest" in lowered:
        return "test_failure"
    if "traceback" in lowered or "runtimeerror" in lowered:
        return "runtime_failure"
    if "resolutionimpossible" in lowered or "cannot install" in lowered:
        return "dependency_resolution"
    if "failed" in lowered or "failure" in lowered:
        return "failed_step"
    if "error" in lowered:
        return "error"
    return "unknown"


def _repo_relative_traceback_path(value: str) -> str:
    matches = _path_like_tokens(value)
    if not matches:
        return value
    for match in matches:
        if match.endswith(".py"):
            return match
    return matches[0]


def _context_lines_around(
    lines: list[str], line_number: int, *, context: int = 3
) -> list[JsonObject]:
    if line_number <= 0:
        return []
    index = line_number - 1
    start = max(0, index - context)
    end = min(len(lines), index + context + 1)
    return [
        {
            "line_number": line_no + 1,
            "text": lines[line_no].rstrip(),
        }
        for line_no in range(start, end)
    ]


def _traceback_exception_summary(log_text: str) -> JsonObject:
    lines = log_text.splitlines()
    active = False
    traceback_start = 0
    last_frame: JsonObject = {}
    summary: JsonObject = {}

    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if "Traceback (most recent call last)" in line:
            active = True
            traceback_start = line_number
            last_frame = {}
            continue

        if not active:
            continue

        frame_match = re.search(
            r'File "([^"]+)", line (\d+), in ([A-Za-z_][A-Za-z0-9_]*)',
            line,
        )
        if frame_match:
            last_frame = {
                "file": frame_match.group(1),
                "line": int(frame_match.group(2)),
                "function": frame_match.group(3),
            }
            continue

        exception_match = re.search(
            r"\b([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):\s*(.+)$",
            line,
        )
        if exception_match:
            owner_file = _repo_relative_traceback_path(str(last_frame.get("file", "")))
            summary = {
                "traceback_start_line": traceback_start,
                "exception_line_number": line_number,
                "exception_type": exception_match.group(1),
                "exception_message": exception_match.group(2).strip(),
                "owner_file": owner_file,
                "owner_line": last_frame.get("line", ""),
                "owner_function": last_frame.get("function", ""),
            }
            active = False

    return summary


def _first_failure_summary(log_text: str, *, context: int = 3) -> JsonObject:
    lines = log_text.splitlines()
    if not lines:
        return {}

    traceback_summary = _traceback_exception_summary(log_text)
    if traceback_summary:
        line_number = int(traceback_summary.get("exception_line_number", 0) or 0)
        exception_type = _string(traceback_summary.get("exception_type"))
        exception_message = _string(traceback_summary.get("exception_message"))
        return {
            "line_number": line_number,
            "line": f"{exception_type}: {exception_message}",
            "tool": "python",
            "kind": "runtime_failure",
            "context": _context_lines_around(lines, line_number, context=context),
            "traceback": traceback_summary,
        }

    for index, line in enumerate(lines):
        stripped = line.strip()
        pytest_node = re.search(
            r"\bFAILED\s+((?:tests|src|tools|docs)/\S+::\S+)",
            stripped,
        )
        if pytest_node:
            return {
                "line_number": index + 1,
                "line": stripped,
                "tool": "pytest",
                "kind": "test_failure",
                "context": _context_lines_around(lines, index + 1, context=context),
            }

    for index, line in enumerate(lines):
        stripped = line.strip()
        ruff_rule = re.search(r"\b([A-Z]\d{3})\s+.+", stripped)
        nearby_context = "\n".join(lines[index + 1 : index + 3])
        if ruff_rule and "-->" in nearby_context:
            return {
                "line_number": index + 1,
                "line": stripped,
                "tool": "ruff",
                "kind": "lint_failure",
                "context": _context_lines_around(lines, index + 1, context=context),
            }

    for index, line in enumerate(lines):
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped or _is_setup_noise_line(stripped):
            continue
        if not any(pattern in lowered for pattern in _EXACT_FAILURE_PATTERNS):
            continue

        if lowered.startswith("run ") and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            next_lowered = next_line.lower()
            if (
                next_line
                and not _is_setup_noise_line(next_line)
                and any(pattern in next_lowered for pattern in _EXACT_FAILURE_PATTERNS)
            ):
                stripped = next_line
                lowered = next_lowered
                index = index + 1

        return {
            "line_number": index + 1,
            "line": stripped,
            "tool": _failure_tool_for_line(stripped),
            "kind": _failure_kind_for_line(stripped),
            "context": _context_lines_around(lines, index + 1, context=context),
        }

    return {}


def _dependency_audit_first_failure(log_text: str) -> JsonObject:

    for index, raw_line in enumerate(log_text.splitlines(), 1):
        line = raw_line.strip()
        if re.search(
            r"Found\s+\d+\s+known\s+vulnerabilit(?:y|ies)\s+in\s+\d+\s+package",
            line,
            flags=re.IGNORECASE,
        ):
            return {
                "line_number": index,
                "line": line,
                "tool": "pip-audit",
                "kind": "dependency_vulnerability",
                "context": [{"line_number": index, "text": raw_line.rstrip()}],
            }
    return {}


def _is_unknown_diagnosis(diagnosis: JsonObject) -> bool:
    code = _string(diagnosis.get("code")).upper()
    title = _string(diagnosis.get("title")).lower()
    return (
        not diagnosis
        or code in {"", "UNKNOWN", "UNKNOWN_REVIEW_REQUIRED"}
        or title in {"", "unknown failure", "failure needs human review"}
    )


def _fallback_check_diagnosis(name: str, first_failure: JsonObject) -> JsonObject:
    lowered = name.lower()
    first_line = _string(first_failure.get("line"))
    first_kind = _string(first_failure.get("kind")).lower()

    if "security" in lowered and first_kind == "check_run_annotation":
        return {
            "code": "SECURITY_FINDING_REVIEW_REQUIRED",
            "title": "Security check annotation requires review",
            "risk_surface": "security",
            "diagnosis": (
                "A failed custom security check produced sanitized GitHub Check Run "
                f"annotation evidence. First collected annotation: {first_line}"
            ),
            "recommended_fix": [
                "Review the current security check annotations for the PR.",
                "Fix the flagged surface or dismiss a reviewed false positive with a reason.",
                "Do not use annotation evidence as authority for automatic remediation.",
            ],
            "proof_commands": [
                "python -m sdetkit security check --root . --format json",
                "python -m pre_commit run -a",
            ],
        }

    if "codeql" in lowered:
        return {
            "code": "CODEQL_SECURITY_REVIEW_REQUIRED",
            "title": "CodeQL security analysis requires review",
            "risk_surface": "security",
            "diagnosis": (
                "CodeQL failed or reported security evidence. Inspect current GitHub "
                "Advanced Security comments and confirm whether each alert is current, "
                "fixed, or a reviewed false positive."
            ),
            "recommended_fix": [
                "Review unresolved GitHub Advanced Security comments on the PR.",
                "For each alert, compare the alert commit SHA with the current PR head.",
                "Fix current true positives or dismiss reviewed false positives with a short reason.",
            ],
            "proof_commands": [
                "python -m sdetkit security check --root . --format json",
                "python -m pre_commit run -a",
            ],
        }

    if "validate" in lowered or "github actions advanced reference" in lowered:
        line = first_line or "No exact failing line was collected from the Validate job log."
        return {
            "code": "VALIDATE_JOB_LOG_REVIEW",
            "title": "Validate job needs exact log review",
            "risk_surface": "workflow",
            "diagnosis": (
                "A Validate job failed before PR Quality could classify the exact product "
                f"failure. First collected signal: {line}"
            ),
            "recommended_fix": [
                "Open the failed Validate job log and extract the first non-setup failure line.",
                "Patch the smallest affected product or test boundary.",
                "Rerun the focused failed test or command before broad pre-commit proof.",
            ],
            "proof_commands": [
                "python -m pre_commit run -a",
                "python -m pytest -q tests/test_pr_quality_evidence_narrative.py tests/test_pr_quality_adaptive_sentinel_workflow.py tests/test_pr_quality_failure_bundle_workflow.py -o addopts=",
            ],
        }

    return {}


def _diagnose_check(record: JsonObject, *, index: int, logs_dir: Path | None) -> JsonObject:
    name = _check_name(record, index)
    log_text = _record_log_text(record, logs_dir, name)
    focused_log_text = _failure_focused_log_text(log_text)
    first_failure = _first_failure_summary(log_text)
    dependency_audit = _extract_dependency_audit_evidence(log_text)
    if dependency_audit:
        first_failure = _dependency_audit_first_failure(log_text) or first_failure
    diagnostic_text = "\n".join(
        part
        for part in [
            f"check_name={name}",
            f"status={_check_status(record)}",
            f"conclusion={_check_conclusion(record)}",
            focused_log_text,
        ]
        if part
    )

    diagnosis = adaptive_diagnosis.analyze_evidence(log_text=diagnostic_text)
    diagnoses = [
        _as_dict(item) for item in _as_list(diagnosis.get("diagnoses")) if isinstance(item, dict)
    ]

    primary = diagnoses[0] if diagnoses else {}
    if (
        _string(first_failure.get("tool")).lower() == "ruff"
        and _string(first_failure.get("kind")).lower() == "lint_failure"
    ):
        for candidate in diagnoses:
            if _string(candidate.get("code")).upper() in {
                "RUFF_FIXABLE_LINT",
                "RUFF_LINT_FAILURE",
            }:
                primary = candidate
                break
    elif _string(first_failure.get("kind")).lower() == "test_failure":
        for candidate in diagnoses:
            if _string(candidate.get("code")).upper() == "PYTEST_ASSERTION_FAILURE":
                primary = candidate
                break
    runtime_traceback = _as_dict(first_failure.get("traceback"))
    if runtime_traceback and (
        not primary
        or _string(primary.get("code")).upper() in {"UNKNOWN", "UNKNOWN_REVIEW_REQUIRED"}
    ):
        exception_type = _string(runtime_traceback.get("exception_type"))
        exception_message = _string(runtime_traceback.get("exception_message"))
        owner_file = _string(runtime_traceback.get("owner_file"))
        owner_line = runtime_traceback.get("owner_line", "")
        location = (
            f"{owner_file}:{owner_line}"
            if owner_file and owner_line
            else owner_file or "unknown location"
        )
        primary = {
            "code": "PYTHON_RUNTIME_EXCEPTION",
            "title": "Python runtime exception",
            "diagnosis": f"{exception_type}: {exception_message} at {location}.",
            "recommended_fix": [
                "Start at the reported owner file and line from the final traceback frame.",
                "Patch the smallest product boundary that explains the exception.",
                "Rerun the exact failed command before broader quality proof.",
            ],
            "proof_commands": [
                "PYTHONPATH=src python tools/maintenance_autopilot.py --owner sherif69-sa --repo DevS69-sdetkit --commit-safe-fixes --max-remediation-attempts 3 --remediation-cooldown-runs 2 --out-dir build/maintenance/autopilot",
                "python -m pre_commit run -a",
                "python -m mypy src",
            ],
        }
    if dependency_audit:
        primary = {
            "code": DEPENDENCY_AUDIT_VULNERABILITY,
            "title": "Dependency audit reported vulnerable packages",
            "diagnosis": (
                f"pip-audit reported {dependency_audit.get('vulnerability_count')} "
                f"known vulnerabilit"
                f"{'y' if dependency_audit.get('vulnerability_count') == 1 else 'ies'} "
                f"in {dependency_audit.get('package_count')} package"
                f"{'' if dependency_audit.get('package_count') == 1 else 's'}."
            ),
            "recommended_fix": [
                "Review pip-audit-report.json for package/advisory/fixed-version details.",
                "Create a dependency-only PR if the finding is not baseline-approved.",
            ],
            "proof_commands": [
                "python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .",
            ],
        }
    fallback = _fallback_check_diagnosis(name, first_failure)
    if fallback and (
        _string(first_failure.get("kind")).lower() == "check_run_annotation"
        or _is_unknown_diagnosis(primary)
    ):
        primary = fallback

    safe_remediation = safe_remediation_eligibility.classify_check_failure(
        name=name,
        diagnosis=primary,
        first_failure=first_failure,
        log_text=log_text,
    )
    head_sha = _record_head_sha(record)
    current_pr_head_sha = _record_current_pr_head_sha(record)
    stale_evidence = bool(head_sha and current_pr_head_sha and head_sha != current_pr_head_sha)
    return {
        "name": name,
        "status": _check_status(record),
        "conclusion": _check_conclusion(record),
        "url": _record_url(record),
        "head_sha": head_sha,
        "current_pr_head_sha": current_pr_head_sha,
        "stale_evidence": stale_evidence,
        "log_collected": bool(log_text.strip()),
        "first_failure": first_failure,
        "first_failure_line": _string(first_failure.get("line")),
        "formatter_changed_files": _formatter_changed_files(log_text),
        "referenced_files": _referenced_failure_files(log_text),
        "outside_changed_files": _outside_changed_files(record, log_text),
        "possible_changed_files_gate_fallout": _possible_changed_files_gate_fallout(
            record,
            log_text,
        ),
        "safe_remediation": safe_remediation,
        "diagnosis": primary,
        "diagnoses": diagnoses,
        "diagnosis_status": diagnosis.get("status", "unknown"),
        "safe_to_auto_fix": bool(safe_remediation.get("safe_to_auto_fix", False)),
        "review_first": bool(dependency_audit),
        "surface": "dependency" if dependency_audit else _surface_for_diagnosis(primary),
        "code": _string(primary.get("code")).upper(),
        "title": _string(primary.get("title")),
        "dependency_audit": dependency_audit,
        "owner_files": (
            DEPENDENCY_AUDIT_OWNER_FILES
            if dependency_audit
            else (
                [_string(runtime_traceback.get("owner_file"))]
                if runtime_traceback and _string(runtime_traceback.get("owner_file"))
                else []
            )
        ),
    }


def _security_review_summary(review_threads_json: Path | None) -> JsonObject:
    if review_threads_json is None:
        return {
            "collected": False,
            "unresolved_findings": 0,
            "source": "",
        }

    if not review_threads_json.exists():
        return {
            "collected": False,
            "unresolved_findings": 0,
            "source": review_threads_json.as_posix(),
        }

    from .security_review_evidence import findings_from_review_threads

    findings = findings_from_review_threads(_read_json(review_threads_json))

    compact_findings = [
        {
            "title": _string(item.get("title")),
            "summary": _string(item.get("summary") or item.get("message")),
            "path": _string(item.get("path") or next(iter(_as_list(item.get("owner_files"))), "")),
            "line": item.get("line", ""),
            "comment_url": _string(item.get("comment_url") or item.get("url")),
            "recommended_commands": [
                str(command)
                for command in _as_list(item.get("recommended_commands"))
                if isinstance(command, str)
            ],
        }
        for item in findings
    ]

    return {
        "collected": True,
        "unresolved_findings": len(findings),
        "findings": compact_findings,
        "source": review_threads_json.as_posix(),
    }


def _open_code_scanning_alerts(payload: Any) -> list[JsonObject]:
    raw_alerts = payload if isinstance(payload, list) else _as_list(_as_dict(payload).get("alerts"))
    return [
        _as_dict(item)
        for item in raw_alerts
        if _as_dict(item) and _string(_as_dict(item).get("state") or "open").lower() == "open"
    ]


def _empty_code_scanning_review(
    *,
    collected: bool,
    collection_status: str,
    source: str,
    collection_reason: str,
    current_head_sha: str,
) -> JsonObject:
    return {
        "collected": collected,
        "collection_status": collection_status,
        "collection_reason": collection_reason,
        "source": source,
        "open_alerts": 0,
        "current_alerts": 0,
        "stale_alerts": 0,
        "unknown_freshness_alerts": 0,
        "current_head_sha": current_head_sha,
        "rule_counts": {},
        "findings": [],
    }


def _code_scanning_review_summary(
    alerts_json: Path | None,
    *,
    current_head_sha: str = "",
) -> JsonObject:
    if alerts_json is None:
        return _empty_code_scanning_review(
            collected=False,
            collection_status="not_requested",
            collection_reason="No code-scanning alert collection artifact was provided.",
            source="",
            current_head_sha=current_head_sha,
        )

    if not alerts_json.exists():
        return _empty_code_scanning_review(
            collected=False,
            collection_status="unavailable",
            collection_reason="The code-scanning alert collection artifact was not found.",
            source=alerts_json.as_posix(),
            current_head_sha=current_head_sha,
        )

    payload = json.loads(alerts_json.read_text(encoding="utf-8"))
    metadata = _as_dict(payload)
    collection_status = _string(metadata.get("collection_status") or "collected").lower()
    collection_reason = _string(metadata.get("collection_reason"))

    if collection_status != "collected":
        return _empty_code_scanning_review(
            collected=False,
            collection_status=collection_status or "unavailable",
            collection_reason=(
                collection_reason or "Code-scanning alert collection did not complete successfully."
            ),
            source=alerts_json.as_posix(),
            current_head_sha=current_head_sha,
        )

    findings: list[JsonObject] = []
    rule_counts: dict[str, int] = {}

    for alert in _open_code_scanning_alerts(payload):
        rule = _as_dict(alert.get("rule"))
        instance = _as_dict(alert.get("most_recent_instance"))
        location = _as_dict(instance.get("location"))
        message = _as_dict(instance.get("message"))
        commit_sha = _string(instance.get("commit_sha"))

        if not commit_sha or not current_head_sha:
            freshness = "unknown"
        elif commit_sha == current_head_sha:
            freshness = "current"
        else:
            freshness = "stale"

        if freshness == "current":
            action = "fix_current_alert_or_dismiss_reviewed_false_positive"
        elif freshness == "stale":
            action = "wait_for_code_scanning_refresh"
        else:
            action = "review_alert_freshness"

        rule_id = _string(rule.get("id") or "unknown")
        rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1

        findings.append(
            {
                "number": alert.get("number", ""),
                "url": _string(alert.get("html_url") or alert.get("url")),
                "rule_id": rule_id,
                "severity": _string(
                    rule.get("security_severity_level") or rule.get("severity") or "unknown"
                ),
                "path": _string(location.get("path")),
                "line": _string(location.get("start_line")),
                "commit_sha": commit_sha,
                "current_head_sha": current_head_sha,
                "freshness": freshness,
                "recommended_action": action,
                "message": _string(message.get("text")),
            }
        )

    return {
        "collected": True,
        "collection_status": "collected",
        "collection_reason": "",
        "source": alerts_json.as_posix(),
        "open_alerts": len(findings),
        "current_alerts": len([item for item in findings if item["freshness"] == "current"]),
        "stale_alerts": len([item for item in findings if item["freshness"] == "stale"]),
        "unknown_freshness_alerts": len(
            [item for item in findings if item["freshness"] == "unknown"]
        ),
        "current_head_sha": current_head_sha,
        "rule_counts": dict(sorted(rule_counts.items())),
        "findings": findings,
    }


def _required_contexts(payload: JsonObject) -> list[str]:
    direct = payload.get("required_contexts")
    if isinstance(direct, list):
        return sorted({str(item).strip() for item in direct if str(item).strip()})

    required_status_checks = _as_dict(payload.get("required_status_checks"))
    contexts = required_status_checks.get("contexts")
    if isinstance(contexts, list):
        return sorted({str(item).strip() for item in contexts if str(item).strip()})

    return []


def _record_identities(record: JsonObject, *, index: int) -> set[str]:
    identities = {
        _check_name(record, index),
        _string(record.get("context")),
        _string(record.get("check_name")),
        _string(record.get("name")),
    }
    return {item for item in identities if item}


def build_check_intelligence(
    *,
    checks_json: Path,
    logs_dir: Path | None = None,
    review_threads_json: Path | None = None,
    code_scanning_alerts_json: Path | None = None,
    current_head_sha: str = "",
) -> JsonObject:
    payload = _read_json(checks_json)
    records = _iter_check_records(payload)
    required_contexts = set(_required_contexts(payload))

    failed_checks: list[JsonObject] = []
    queued_checks: list[JsonObject] = []
    cancelled_checks: list[JsonObject] = []
    startup_failures: list[JsonObject] = []
    seen_identities: set[str] = set()

    for index, record in enumerate(records):
        seen_identities.update(_record_identities(record, index=index))
        check = {
            "name": _check_name(record, index),
            "status": _check_status(record),
            "conclusion": _check_conclusion(record),
            "required": _check_required(record),
            "url": _record_url(record),
        }

        if _is_failed(record):
            diagnosed = _diagnose_check(record, index=index, logs_dir=logs_dir)
            failed_checks.append(diagnosed)

        if _is_queued_or_pending(record):
            queued_checks.append(check)

        if _is_cancelled(record):
            cancelled_checks.append(check)

        if _is_startup_failure(record):
            startup_failures.append(check)

    missing_required_contexts = sorted(required_contexts - seen_identities)
    for context in missing_required_contexts:
        queued_checks.append(
            {
                "name": context,
                "status": "queued",
                "conclusion": "",
                "required": True,
                "missing_required_context": True,
                "url": "",
            }
        )

    return {
        "schema_version": CHECK_INTELLIGENCE_SCHEMA_VERSION,
        "checks_seen": len(records) + len(missing_required_contexts),
        "required_contexts": sorted(required_contexts),
        "missing_required_contexts": missing_required_contexts,
        "failed_checks": failed_checks,
        "queued_checks": queued_checks,
        "cancelled_checks": cancelled_checks,
        "startup_failures": startup_failures,
        "security_review": _security_review_summary(review_threads_json),
        "code_scanning_review": _code_scanning_review_summary(
            code_scanning_alerts_json,
            current_head_sha=current_head_sha,
        ),
        "current_head_sha": current_head_sha,
    }


def _primary_failed_check(intelligence: JsonObject) -> JsonObject:
    failed = [_as_dict(item) for item in _as_list(intelligence.get("failed_checks"))]
    if not failed:
        return {}

    current_pr_head_sha = _string(
        intelligence.get("current_pr_head_sha") or intelligence.get("pr_head_sha")
    )

    def score(check: JsonObject) -> tuple[int, int, int, int]:
        diagnosis = _as_dict(check.get("diagnosis"))
        safe = 1 if bool(check.get("safe_to_auto_fix", False)) else 0
        unsafe_priority = 0 if safe else 1
        stale_priority = (
            0
            if _is_stale_check_evidence(
                check,
                current_pr_head_sha=current_pr_head_sha,
            )
            else 1
        )
        actionable_priority = (
            0 if bool(check.get("possible_changed_files_gate_fallout", False)) else 1
        )
        surface_priority = {
            "security": 100,
            "dependency": 95,
            "release": 90,
            "workflow": 85,
            "cli": 80,
            "tests": 75,
            "docs": 70,
            "quality": 40,
            "unknown": 0,
        }
        surface = _surface_for_diagnosis(diagnosis)
        return (
            stale_priority,
            actionable_priority,
            unsafe_priority,
            surface_priority.get(surface, 0),
        )

    return max(failed, key=score)


def _surface_for_diagnosis(diagnosis: JsonObject) -> str:
    explicit = _string(diagnosis.get("risk_surface") or diagnosis.get("surface")).lower()
    if explicit:
        return explicit

    code = _string(diagnosis.get("code")).upper()
    if code in _DIAGNOSIS_SURFACES:
        return _DIAGNOSIS_SURFACES[code]

    text = " ".join(
        [
            _string(diagnosis.get("title")),
            _string(diagnosis.get("diagnosis")),
            " ".join(str(item) for item in _as_list(diagnosis.get("proof_commands"))),
            " ".join(str(item) for item in _as_list(diagnosis.get("recommended_fix"))),
        ]
    ).lower()

    if any(token in text for token in ("security", "secret", "vulnerability")):
        return "security"
    if any(token in text for token in ("dependency", "resolver", "pip", "requirements")):
        return "dependency"
    if any(token in text for token in ("release", "twine", "publish", "dist/")):
        return "release"
    if any(token in text for token in ("workflow", "github actions", "yaml")):
        return "workflow"
    if any(token in text for token in ("cli", "entry point", "argparse")):
        return "cli"
    if any(token in text for token in ("pytest", "assertion", "test")):
        return "tests"
    if any(token in text for token in ("docs", "mkdocs", "documentation")):
        return "docs"
    if any(token in text for token in ("ruff", "format", "mypy", "coverage", "pre-commit")):
        return "quality"
    return "unknown"


def _safe_fix_reason(code: str, safe: bool) -> str:
    if safe and code in _SAFE_AUTO_FIX_CODES:
        return "diagnosis is approved for narrow mechanical safe-fix planning"
    if safe:
        return "diagnosis reported safe_to_auto_fix=true"
    return "diagnosis is review-first or not approved for automatic mutation"


def _diagnosis_commands(diagnosis: JsonObject, key: str) -> list[str]:
    return [str(item) for item in _as_list(diagnosis.get(key)) if isinstance(item, str)]


def build_action_report(intelligence: JsonObject) -> JsonObject:
    failed = _as_list(intelligence.get("failed_checks"))
    queued = _as_list(intelligence.get("queued_checks"))
    startup = _as_list(intelligence.get("startup_failures"))

    security_review = _as_dict(intelligence.get("security_review"))
    security_findings = [
        _as_dict(item)
        for item in _as_list(security_review.get("findings"))
        if isinstance(item, dict)
    ]
    unresolved_security = int(security_review.get("unresolved_findings", 0) or 0)
    if unresolved_security and not failed:
        finding = security_findings[0] if security_findings else {}
        commands = [
            str(command)
            for command in _as_list(finding.get("recommended_commands"))
            if isinstance(command, str)
        ]
        return {
            "schema_version": ACTION_REPORT_SCHEMA_VERSION,
            "status": "review_required",
            "primary_blocker": {
                "check": "GitHub security review",
                "title": _string(finding.get("title") or "Security review requires action"),
                "surface": "security",
                "impact": _string(
                    finding.get("summary")
                    or "An unresolved security review finding must be fixed or dismissed with a review reason."
                ),
                "code": "SECURITY_REVIEW_FINDING",
                "url": _string(finding.get("comment_url")),
                "path": _string(finding.get("path")),
                "line": finding.get("line", ""),
            },
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "security review findings are review-first and cannot be auto-dismissed",
            },
            "recommended_actions": commands
            or [
                "Review unresolved GitHub Advanced Security comments on the PR.",
                "Fix the flagged surface or dismiss the false positive with a review reason.",
            ],
            "proof_commands": [
                "python -m sdetkit security check --root . --format json",
                "python -m pre_commit run -a",
            ],
            "evidence": {
                "failed_check_count": 0,
                "queued_check_count": len(queued),
                "required_queued_check_count": len(
                    [
                        _as_dict(item)
                        for item in queued
                        if bool(_as_dict(item).get("required", False))
                    ]
                ),
                "startup_failure_count": len(startup),
                "required_startup_failure_count": len(
                    [
                        _as_dict(item)
                        for item in startup
                        if bool(_as_dict(item).get("required", False))
                    ]
                ),
                "security_review": security_review,
                "code_scanning_review": intelligence.get("code_scanning_review", {}),
            },
        }

    code_scanning_review = _as_dict(intelligence.get("code_scanning_review"))
    current_code_scanning_findings = [
        _as_dict(item)
        for item in _as_list(code_scanning_review.get("findings"))
        if isinstance(item, dict) and _string(_as_dict(item).get("freshness")).lower() == "current"
    ]
    if current_code_scanning_findings and not failed:
        finding = current_code_scanning_findings[0]
        path = _string(finding.get("path"))
        line = _string(finding.get("line"))
        location = f"{path}:{line}" if path and line else path
        rule_id = _string(finding.get("rule_id") or "unknown")
        severity = _string(finding.get("severity") or "unknown")
        title = (
            f"Current code scanning alert requires action in {location}"
            if location
            else "Current code scanning alert requires action"
        )
        message = _string(finding.get("message"))
        impact = (
            message
            or "A current PR-owned code scanning alert must be fixed or dismissed with a review reason."
        )
        return {
            "schema_version": ACTION_REPORT_SCHEMA_VERSION,
            "status": "review_required",
            "primary_blocker": {
                "check": "GitHub code scanning",
                "title": title,
                "surface": "security",
                "impact": impact,
                "code": CODE_SCANNING_CURRENT_ALERT,
                "url": _string(finding.get("url")),
                "path": path,
                "line": line,
                "rule_id": rule_id,
                "severity": severity,
            },
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": (
                    "current code-scanning alerts are review-first and cannot be auto-dismissed"
                ),
            },
            "recommended_actions": [
                "Review the current GitHub code scanning alert on the PR.",
                "Fix the flagged surface or dismiss the reviewed false positive with a reason.",
            ],
            "proof_commands": [
                "python -m sdetkit security check --root . --format json",
                "python -m pre_commit run -a",
            ],
            "evidence": {
                "failed_check_count": 0,
                "queued_check_count": len(queued),
                "required_queued_check_count": len(
                    [
                        _as_dict(item)
                        for item in queued
                        if bool(_as_dict(item).get("required", False))
                    ]
                ),
                "startup_failure_count": len(startup),
                "required_startup_failure_count": len(
                    [
                        _as_dict(item)
                        for item in startup
                        if bool(_as_dict(item).get("required", False))
                    ]
                ),
                "security_review": security_review,
                "code_scanning_review": code_scanning_review,
            },
        }

    if failed:
        check = _primary_failed_check(intelligence)
        diagnosis = _as_dict(check.get("diagnosis"))
        code = _string(diagnosis.get("code")).upper()
        title = _string(diagnosis.get("title") or code or check.get("name"))
        surface = _surface_for_diagnosis(diagnosis)
        safe = bool(check.get("safe_to_auto_fix", False)) and code in _SAFE_AUTO_FIX_CODES
        status = "safe_fix_available" if safe else "review_required"

        return {
            "schema_version": ACTION_REPORT_SCHEMA_VERSION,
            "status": status,
            "primary_blocker": {
                "check": check.get("name", ""),
                "title": title,
                "surface": surface,
                "impact": _string(
                    diagnosis.get("diagnosis")
                    or "The check failed before the PR could be treated as fully proven."
                ),
                "code": code,
                "url": check.get("url", ""),
                "first_failure": check.get("first_failure", {}),
                "first_failure_line": check.get("first_failure_line", ""),
                "head_sha": check.get("head_sha", ""),
                "current_pr_head_sha": check.get("current_pr_head_sha", ""),
                "stale_evidence": check.get("stale_evidence", False),
                "formatter_changed_files": check.get("formatter_changed_files", []),
                "referenced_files": check.get("referenced_files", []),
                "outside_changed_files": check.get("outside_changed_files", []),
                "possible_changed_files_gate_fallout": check.get(
                    "possible_changed_files_gate_fallout",
                    False,
                ),
                "safe_remediation": check.get("safe_remediation", {}),
                "safe_to_auto_fix": check.get("safe_to_auto_fix", False),
                "review_first": bool(check.get("review_first", False)),
                "dependency_audit": check.get("dependency_audit", {}),
                "owner_files": check.get("owner_files", []),
            },
            "automation": {
                "attempted": False,
                "allowed": safe,
                "reason": _safe_fix_reason(code, safe),
            },
            "recommended_actions": _diagnosis_commands(diagnosis, "recommended_fix"),
            "proof_commands": _diagnosis_commands(diagnosis, "proof_commands"),
            "evidence": {
                "failed_check_count": len(failed),
                "queued_check_count": len(queued),
                "required_queued_check_count": len(
                    [
                        _as_dict(item)
                        for item in queued
                        if bool(_as_dict(item).get("required", False))
                    ]
                ),
                "startup_failure_count": len(startup),
                "required_startup_failure_count": len(
                    [
                        _as_dict(item)
                        for item in startup
                        if bool(_as_dict(item).get("required", False))
                    ]
                ),
                "security_review": intelligence.get("security_review", {}),
                "code_scanning_review": intelligence.get("code_scanning_review", {}),
            },
        }

    required_queued = [
        _as_dict(item) for item in queued if bool(_as_dict(item).get("required", False))
    ]
    required_startup = [
        _as_dict(item) for item in startup if bool(_as_dict(item).get("required", False))
    ]

    if required_queued or required_startup:
        blocker = _as_dict((required_queued or required_startup)[0])
        return {
            "schema_version": ACTION_REPORT_SCHEMA_VERSION,
            "status": "incomplete",
            "primary_blocker": {
                "check": _string(blocker.get("name")),
                "title": "Required checks are not complete",
                "surface": "workflow",
                "impact": "The PR cannot be treated as fully proven while required checks are queued, pending, or failed to start.",
                "code": "CHECKS_INCOMPLETE",
                "url": _string(blocker.get("url")),
            },
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "required check completion is needed before remediation or green signoff",
            },
            "recommended_actions": [
                "Wait for required queued checks to complete or inspect the workflow-start issue.",
                "Do not treat the PR as green until required check intelligence is complete.",
            ],
            "proof_commands": [],
            "evidence": {
                "failed_check_count": 0,
                "queued_check_count": len(queued),
                "required_queued_check_count": len(required_queued),
                "startup_failure_count": len(startup),
                "required_startup_failure_count": len(required_startup),
                "security_review": intelligence.get("security_review", {}),
                "code_scanning_review": intelligence.get("code_scanning_review", {}),
            },
        }

    return {
        "schema_version": ACTION_REPORT_SCHEMA_VERSION,
        "status": "green",
        "primary_blocker": {},
        "automation": {
            "attempted": False,
            "allowed": False,
            "reason": "no remediation needed",
        },
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {
            "failed_check_count": 0,
            "queued_check_count": len(queued),
            "required_queued_check_count": 0,
            "startup_failure_count": len(startup),
            "required_startup_failure_count": 0,
            "security_review": intelligence.get("security_review", {}),
            "code_scanning_review": intelligence.get("code_scanning_review", {}),
        },
    }


def render_action_report(report: JsonObject) -> str:
    status = _string(report.get("status"))
    lines = [
        "# SDETKit Check Intelligence Action Report",
        "",
        f"Status: `{status}`",
        "",
    ]

    primary = _as_dict(report.get("primary_blocker"))
    if primary:
        lines.extend(
            [
                "## Primary blocker",
                "",
                f"- Check: `{primary.get('check', '')}`",
                f"- Title: {primary.get('title', '')}",
                f"- Surface: `{primary.get('surface', '')}`",
                f"- Code: `{primary.get('code', '')}`",
                f"- Impact: {primary.get('impact', '')}",
                "",
            ]
        )
    else:
        lines.extend(["## Primary blocker", "", "- none", ""])

    automation = _as_dict(report.get("automation"))
    lines.extend(
        [
            "## Automation decision",
            "",
            f"- Attempted: `{str(automation.get('attempted', False)).lower()}`",
            f"- Allowed: `{str(automation.get('allowed', False)).lower()}`",
            f"- Reason: {automation.get('reason', '')}",
            "",
            "## Recommended actions",
            "",
        ]
    )
    actions = [str(item) for item in _as_list(report.get("recommended_actions"))]
    lines.extend([f"- {item}" for item in actions] or ["- none"])
    lines.extend(["", "## Proof commands", ""])
    commands = [str(item) for item in _as_list(report.get("proof_commands"))]
    lines.extend([f"- `{item}`" for item in commands] or ["- none"])
    lines.append("")
    return "\n".join(lines)


def write_artifacts(
    *,
    intelligence: JsonObject,
    action_report: JsonObject,
    out_dir: Path,
) -> JsonObject:
    out_dir.mkdir(parents=True, exist_ok=True)
    check_path = out_dir / "check-intelligence.json"
    action_path = out_dir / "action-report.json"
    markdown_path = out_dir / "action-report.md"

    _write_json(check_path, intelligence)
    _write_json(action_path, action_report)
    markdown_path.write_text(render_action_report(action_report), encoding="utf-8")

    return {
        "check_intelligence": check_path.as_posix(),
        "action_report": action_path.as_posix(),
        "action_report_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.check_intelligence")
    parser.add_argument("--checks-json", type=Path, required=True)
    parser.add_argument("--logs-dir", type=Path)
    parser.add_argument("--review-threads-json", type=Path)
    parser.add_argument("--code-scanning-alerts-json", type=Path)
    parser.add_argument("--current-head-sha", default="")
    parser.add_argument("--out-dir", type=Path, default=Path("build/pr-quality"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    intelligence = build_check_intelligence(
        checks_json=args.checks_json,
        logs_dir=args.logs_dir,
        review_threads_json=args.review_threads_json,
        code_scanning_alerts_json=args.code_scanning_alerts_json,
        current_head_sha=args.current_head_sha,
    )
    action_report = build_action_report(intelligence)
    artifacts = write_artifacts(
        intelligence=intelligence,
        action_report=action_report,
        out_dir=args.out_dir,
    )
    sys.stdout.write(json.dumps(artifacts, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
