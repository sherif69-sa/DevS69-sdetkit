from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from sdetkit import safe_remediation_eligibility

from . import adaptive_diagnosis

CHECK_INTELLIGENCE_SCHEMA_VERSION = "sdetkit.pr_quality.check_intelligence.v1"
ACTION_REPORT_SCHEMA_VERSION = "sdetkit.pr_quality.action_report.v1"

JsonObject = dict[str, Any]


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
    "DOCS_BUILD_CONTRACT": "docs",
    "PYTEST_ASSERTION_FAILURE": "tests",
    "PYTEST_IMPORT_FAILURE": "tests",
    "PRE_COMMIT_FORMAT_DRIFT": "quality",
    "RUFF_FIXABLE_LINT": "quality",
    "RUFF_LINT_FAILURE": "quality",
    "MYPY_TYPE_CONTRACT_DRIFT": "quality",
    "COVERAGE_GATE_REGRESSION": "quality",
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
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip().lower()).strip("-")
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
    compact_slug = slug.replace("-", "")
    exact_candidates = [
        logs_dir / f"{slug}.log",
        logs_dir / f"{slug}.txt",
        logs_dir / f"{name}.log",
        logs_dir / f"{name}.txt",
    ]
    for candidate in exact_candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="ignore")

    name_tokens = {token for token in slug.split("-") if token}
    readable_files = [candidate for candidate in sorted(logs_dir.rglob("*")) if candidate.is_file()]
    for candidate in readable_files:
        candidate_slug = _slug(candidate.stem)
        candidate_compact = candidate_slug.replace("-", "")
        candidate_tokens = {token for token in candidate_slug.split("-") if token}

        if (
            slug == candidate_slug
            or slug in candidate_slug
            or candidate_slug in slug
            or compact_slug == candidate_compact
            or compact_slug in candidate_compact
            or candidate_compact in compact_slug
            or (name_tokens and name_tokens.issubset(candidate_tokens))
        ):
            return candidate.read_text(encoding="utf-8", errors="ignore")

    if len(readable_files) == 1:
        return readable_files[0].read_text(encoding="utf-8", errors="ignore")

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
    "no tests ran",
    "found 1 error",
    "found ",
    "ruff",
    "mypy",
    "pytest",
)


_FAILURE_LINE_PATTERNS = _EXACT_FAILURE_PATTERNS


def _failure_tool_for_line(line: str) -> str:
    lowered = line.lower()
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


def _first_failure_summary(log_text: str, *, context: int = 3) -> JsonObject:
    lines = log_text.splitlines()
    if not lines:
        return {}

    for index, line in enumerate(lines):
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            continue
        if not any(pattern in lowered for pattern in _EXACT_FAILURE_PATTERNS):
            continue

        if lowered.startswith("run ") and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            next_lowered = next_line.lower()
            if next_line and any(pattern in next_lowered for pattern in _EXACT_FAILURE_PATTERNS):
                stripped = next_line
                lowered = next_lowered
                index = index + 1

        start = max(0, index - context)
        end = min(len(lines), index + context + 1)
        context_lines = [
            {
                "line_number": line_no + 1,
                "text": lines[line_no].rstrip(),
            }
            for line_no in range(start, end)
        ]

        return {
            "line_number": index + 1,
            "line": stripped,
            "tool": _failure_tool_for_line(stripped),
            "kind": _failure_kind_for_line(stripped),
            "context": context_lines,
        }

    return {}


def _diagnose_check(record: JsonObject, *, index: int, logs_dir: Path | None) -> JsonObject:
    name = _check_name(record, index)
    log_text = _record_log_text(record, logs_dir, name)
    focused_log_text = _failure_focused_log_text(log_text)
    first_failure = _first_failure_summary(log_text)
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
    safe_remediation = safe_remediation_eligibility.classify_check_failure(
        name=name,
        diagnosis=primary,
        first_failure=first_failure,
        log_text=log_text,
    )
    return {
        "name": name,
        "status": _check_status(record),
        "conclusion": _check_conclusion(record),
        "url": _record_url(record),
        "log_collected": bool(log_text.strip()),
        "first_failure": first_failure,
        "first_failure_line": _string(first_failure.get("line")),
        "safe_remediation": safe_remediation,
        "diagnosis": primary,
        "diagnoses": diagnoses,
        "diagnosis_status": diagnosis.get("status", "unknown"),
        "safe_to_auto_fix": bool(safe_remediation.get("safe_to_auto_fix", False)),
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

    try:
        from .security_review_evidence import findings_from_review_threads

        findings = findings_from_review_threads(review_threads_json)
    except Exception:
        findings = []

    compact_findings = [
        {
            "title": _string(item.get("title")),
            "summary": _string(item.get("summary") or item.get("message")),
            "path": _string(item.get("path")),
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
    }


def _primary_failed_check(intelligence: JsonObject) -> JsonObject:
    failed = [_as_dict(item) for item in _as_list(intelligence.get("failed_checks"))]
    if not failed:
        return {}

    def score(check: JsonObject) -> tuple[int, int]:
        diagnosis = _as_dict(check.get("diagnosis"))
        safe = 1 if bool(check.get("safe_to_auto_fix", False)) else 0
        unsafe_priority = 0 if safe else 1
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
        return (unsafe_priority, surface_priority.get(surface, 0))

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
                "safe_remediation": check.get("safe_remediation", {}),
                "safe_to_auto_fix": check.get("safe_to_auto_fix", False),
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
    parser.add_argument("--out-dir", type=Path, default=Path("build/pr-quality"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    intelligence = build_check_intelligence(
        checks_json=args.checks_json,
        logs_dir=args.logs_dir,
        review_threads_json=args.review_threads_json,
    )
    action_report = build_action_report(intelligence)
    artifacts = write_artifacts(
        intelligence=intelligence,
        action_report=action_report,
        out_dir=args.out_dir,
    )
    print(json.dumps(artifacts, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
