from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sdetkit.current_head_failure_bundle import (
    build_current_head_failure_bundle,
    write_current_head_failure_bundle,
)
from sdetkit.pr_comment_failure_families import render_comment_failure_families

JsonObject = dict[str, Any]

CANONICAL_REVIEW_STATES = (
    "waiting",
    "blocked",
    "review",
    "ready",
    "stale",
    "invalid",
)
KNOWN_ACTION_REPORT_STATUSES = {
    "green",
    "incomplete",
    "review_required",
    "safe_fix_available",
}

TRUSTED_HISTORY = "_".join(("trusted", "history"))
FLAKY_TEST_REGISTRY_COLLECTION_STATUS = "_".join(
    ("flaky", "test", "registry", "collection", "status")
)
FLAKY_TEST_REGISTRY_STATUS = "_".join(("flaky", "test", "registry", "status"))
FLAKY_TEST_REGISTRY_ENTRY_COUNT = "_".join(("flaky", "test", "registry", "entry", "count"))
FLAKY_TEST_REGISTRY_OBSERVATION_STATUS = "_".join(
    ("flaky", "test", "registry", "observation", "status")
)
FLAKY_TEST_REGISTRY_OBSERVATIONS_COLLECTED = "_".join(
    ("flaky", "test", "registry", "observations", "collected")
)
FLAKY_TEST_REGISTRY_PRODUCER_VETTED = "_".join(("flaky", "test", "registry", "producer", "vetted"))
FLAKY_TEST_REGISTRY_RAW_TEST_IDENTITY_EMITTED = "_".join(
    ("flaky", "test", "registry", "raw", "test", "identity", "emitted")
)
FLAKY_TEST_REGISTRY_CURRENT_PR_DECISION_INPUT = "_".join(
    ("flaky", "test", "registry", "current", "pr", "decision", "input")
)
TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY = "_".join(
    ("trusted", "diagnostic", "signal", "snapshot", "history")
)
BASE_ANCESTRY_VERIFIED = "_".join(("base", "ancestry", "verified"))
LIVE_PROVEN_RECORD_COUNT = "_".join(("live", "contract", "proven", "record", "count"))
PRIOR_HISTORY_READ_ONLY_INPUT = "_".join(("prior", "history", "is", "read", "only", "input"))
PROOF_COMMANDS_EXECUTED_BY_READER = "_".join(("proof", "commands", "executed", "by", "reader"))
TRUSTED_HISTORY_COLLECTION_STATUS = "_".join(("trusted", "history", "collection", "status"))
TRUSTED_HISTORY_STATUS = "_".join(("trusted", "history", "status"))
CONTROLLED_VALIDATION_RECORD_COUNT = "_".join(("controlled", "validation", "record", "count"))
CONTROLLED_VALIDATION_SCENARIO_COUNT = "_".join(("controlled", "validation", "scenario", "count"))
CONTROLLED_STRUCTURALLY_VERIFIED_COUNT = "_".join(
    ("controlled", "structurally", "verified", "count")
)
CONTROLLED_REVIEW_FIRST_COUNT = "_".join(("controlled", "review", "first", "count"))
TRUSTED_HISTORY_RECORD_COUNT = "_".join(("trusted", "history", "record", "count"))
TRUSTED_HISTORY_BASE_ANCESTRY_VERIFIED = "_".join(
    ("trusted", "history", "base", "ancestry", "verified")
)
TRUSTED_HISTORY_PRIOR_INPUT_READ_ONLY = "_".join(
    ("trusted", "history", "prior", "input", "read", "only")
)
TRUSTED_HISTORY_AUTOMATION_ALLOWED = "_".join(("trusted", "history", "automation", "allowed"))
TRUSTED_HISTORY_MERGE_AUTHORIZED = "_".join(("trusted", "history", "merge", "authorized"))
TRUSTED_HISTORY_SEMANTIC_EQUIVALENCE_PROVEN = "_".join(
    ("trusted", "history", "semantic", "equivalence", "proven")
)
AUTOMATIC_SECURITY_FIX_ALLOWED = "_".join(("automatic", "security", "fix", "allowed"))
AUTOMATIC_DISMISSAL_ALLOWED = "_".join(("automatic", "dismissal", "allowed"))
TRUSTED_REVIEWED_DISPOSITION_HISTORY = "_".join(("trusted", "reviewed", "disposition", "history"))
TRUSTED_REVIEWED_DISPOSITION_CONTEXT = "_".join(("trusted", "reviewed", "disposition", "context"))
MATCHING_REVIEWED_DISPOSITION_COUNT = "_".join(("matching", "reviewed", "disposition", "count"))
HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION = "_".join(
    ("historical", "disposition", "authorizes", "current", "action")
)
CURRENT_FINDINGS = "_".join(("current", "findings"))
STALE_FINDINGS = "_".join(("stale", "findings"))
TRUE_POSITIVE_FIX_REQUIRED = "_".join(("true", "positive", "fix", "required"))
CURRENT_ALERTS = "_".join(("current", "alerts"))
STALE_ALERTS = "_".join(("stale", "alerts"))
UNRESOLVED_FINDINGS = "_".join(("unresolved", "findings"))
STALE_ONLY_CODE_SCANNING = "_".join(("stale", "only", "code", "scanning"))
STALE_ONLY_SECURITY_SIGNAL = "_".join(("stale", "only", "security", "signal"))
WAIT_FOR_CODE_SCANNING_REFRESH = "_".join(("wait", "for", "code", "scanning", "refresh"))


FAILED_STEP_EVIDENCE_KEY = "_".join(("failed", "step", "evidence"))
JOB_STEP_CONFIRMATION_KEY = "_".join(("job", "step", "confirmation"))
ARTIFACT_EVIDENCE_KEY = "_".join(("artifact", "evidence"))

BANNED_EDUCATIONAL_PHRASES = (
    "Quality is green, so the review focus is not coverage.",
    "The comment must guide maintainers toward the changed risk surface.",
    "Review the security evidence against the PR diff.",
    "Confirm the graph findings match the changed files and artifacts.",
    "PR Quality evidence affects the comment maintainers use",
)


def _render_failure_family_coverage_from_report_text(report_text: str) -> list[str]:
    rendered = render_comment_failure_families(report_text)
    if rendered == "Additional failure families: none detected":
        return ["## Failure family coverage", "", "- none detected", ""]
    return ["## Failure family coverage", "", *rendered.splitlines(), ""]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _as_dict(payload)


def _read_jsonl(path: Path | None) -> list[JsonObject]:
    if path is None or not path.exists():
        return []

    records: list[JsonObject] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            msg = f"expected JSON object on line {line_number} in {path}"
            raise ValueError(msg)
        records.append(payload)

    return records


def _string(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _trajectory_authority_key(*parts: str) -> str:
    return "_".join(("trajectory", "authority", *parts))


def _repo_memory_trajectory_authority_key(*parts: str) -> str:
    return "_".join(("repo", "memory", "trajectory", "authority", *parts))


def _protected_verifier_evidence_key(*parts: str) -> str:
    return "_".join(parts)


PROTECTED_VERIFIER_RUNTIME_PROOF_EVIDENCE = _protected_verifier_evidence_key(
    "runtime", "proof", "evidence"
)
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_REPLAY_EVIDENCE = _protected_verifier_evidence_key(
    "benchmark", "contract", "replay", "evidence"
)


def _status_title(status: str) -> str:
    return {
        "green": "Green",
        "incomplete": "Checks incomplete",
        "review_required": "Action required",
        "safe_fix_available": "Safe fix available",
    }.get(status, status.replace("_", " ").title() or "Unknown")


def _result_title(
    status: str,
    *,
    evidence_signal_present: bool,
    evidence_review_required: bool,
) -> str:
    base = _status_title(status)
    if status != "green":
        return base
    if evidence_review_required:
        return f"{base} with evidence review"
    if evidence_signal_present:
        return f"{base} with proof signal"
    return base


def _quality_lines(evidence_narrative: JsonObject) -> list[str]:
    quality = _as_dict(evidence_narrative.get("quality"))
    if not quality:
        return []

    ok = quality.get("ok")
    coverage = (
        quality.get("coverage")
        or quality.get("coverage_percent")
        or quality.get("coverage_pct")
        or ""
    )

    lines: list[str] = []
    if ok is True:
        lines.append("- Quality gate: `passed`")
    elif ok is False:
        lines.append("- Quality gate: `failed`")

    if coverage not in {"", None}:
        lines.append(f"- Coverage: `{coverage}`")

    return lines


def _safe_fix_outcome_lines(outcome: JsonObject) -> list[str]:
    if not outcome:
        return ["- none"]

    files = [_string(item) for item in _as_list(outcome.get("affected_files")) if _string(item)]
    proof_commands = [
        _string(item) for item in _as_list(outcome.get("proof_commands")) if _string(item)
    ]

    lines = [
        f"- Status: `{_string(outcome.get('status') or 'unknown')}`",
        f"- Attempted: `{str(bool(outcome.get('attempted', False))).lower()}`",
        f"- Remediation OK: `{str(bool(outcome.get('remediation_ok', False))).lower()}`",
        f"- Committed: `{str(bool(outcome.get('committed', False))).lower()}`",
        f"- Pushed: `{str(bool(outcome.get('pushed', False))).lower()}`",
        f"- Commit SHA: `{_string(outcome.get('commit_sha') or 'none')}`",
        "- Files: " + (", ".join(f"`{item}`" for item in files) if files else "`none`"),
        f"- Reason: {_string(outcome.get('reason') or 'none')}",
    ]

    if proof_commands:
        lines.append("- Proof after fix:")
        lines.extend(f"  - `{item}`" for item in proof_commands)
    else:
        lines.append("- Proof after fix: none")

    return lines


def _remediation_refresh_lines(refresh: JsonObject) -> list[str]:
    if not refresh:
        return ["none"]

    lines = [
        f"- Safe fix pushed: `{str(bool(refresh.get('safe_fix_pushed', False))).lower()}`",
        f"- Safe fix committed: `{str(bool(refresh.get('safe_fix_committed', False))).lower()}`",
        f"- Safe fix commit SHA: `{_string(refresh.get('safe_fix_commit_sha') or 'none')}`",
        f"- Previous head SHA: `{_string(refresh.get('previous_head_sha') or 'unknown')}`",
        f"- Refreshed head SHA: `{_string(refresh.get('refreshed_head_sha') or 'unknown')}`",
    ]

    if bool(refresh.get("safe_fix_pushed", False)):
        lines.append("- Safe fix pushed to branch.")

    proof_after_fix_passed = bool(refresh.get("proof_after_fix_passed", False))
    proof_after_fix_failed = bool(refresh.get("proof_after_fix_failed", False))
    proof_after_fix_started = bool(refresh.get("proof_after_fix_started", False))
    if proof_after_fix_passed:
        proof_result = "passed"
    elif proof_after_fix_failed:
        proof_result = "failed"
    elif proof_after_fix_started:
        proof_result = "started"
    else:
        proof_result = "not_started"

    lines.append(f"- Proof after fix result: `{proof_result}`")

    failed = [
        _string(item) for item in _as_list(refresh.get("remaining_failed_checks")) if _string(item)
    ]
    blockers = [
        _string(item)
        for item in _as_list(refresh.get("remaining_review_first_blockers"))
        if _string(item)
    ]
    if failed:
        lines.append("- Remaining failed checks: " + ", ".join(f"`{item}`" for item in failed[:8]))
    else:
        lines.append("- Remaining failed checks: none")

    if blockers:
        lines.append("- Remaining blockers: " + ", ".join(f"`{item}`" for item in blockers[:8]))
    else:
        lines.append("- Remaining blockers: none")

    lines.append(f"- Merge assessment: `{_string(refresh.get('merge_assessment') or 'unknown')}`")
    return lines


def _evidence_lines(check_intelligence: JsonObject, action_report: JsonObject) -> list[str]:
    security = _as_dict(
        check_intelligence.get("security_review")
        or _as_dict(action_report.get("evidence")).get("security_review")
    )
    failed_count = len(_as_list(check_intelligence.get("failed_checks")))
    queued = [_as_dict(item) for item in _as_list(check_intelligence.get("queued_checks"))]
    startup = [_as_dict(item) for item in _as_list(check_intelligence.get("startup_failures"))]
    queued_count = len(queued)
    startup_count = len(startup)
    required_queued_count = len([item for item in queued if bool(item.get("required", False))])
    required_startup_count = len([item for item in startup if bool(item.get("required", False))])
    missing_required_count = len(_as_list(check_intelligence.get("missing_required_contexts")))
    checks_seen = _int(check_intelligence.get("checks_seen"))
    unresolved_security = _int(security.get("unresolved_findings"))
    code_scanning = _as_dict(
        check_intelligence.get("code_scanning_review")
        or _as_dict(action_report.get("evidence")).get("code_scanning_review")
    )

    lines = [
        f"- Checks seen: `{checks_seen}`",
        f"- Failed checks: `{failed_count}`",
        f"- Queued checks: `{queued_count}`",
        f"- Required queued checks: `{required_queued_count}`",
        f"- Missing required contexts: `{missing_required_count}`",
        f"- Startup failures: `{startup_count}`",
        f"- Required startup failures: `{required_startup_count}`",
    ]

    if security:
        collected = "true" if bool(security.get("collected", False)) else "false"
        lines.append(f"- Security review collected: `{collected}`")
        lines.append(f"- Unresolved security findings: `{unresolved_security}`")

    if code_scanning:
        collected = "true" if bool(code_scanning.get("collected", False)) else "false"
        collection_status = _string(
            code_scanning.get("collection_status")
            or ("collected" if collected == "true" else "unavailable")
        )
        collection_reason = _string(code_scanning.get("collection_reason"))

        lines.append(f"- Code scanning review collected: `{collected}`")
        lines.append(f"- Code scanning collection status: `{collection_status}`")
        if collection_reason:
            lines.append(f"- Code scanning collection reason: {collection_reason}")
        lines.append(f"- Open code scanning alerts: `{_int(code_scanning.get('open_alerts'))}`")
        lines.append(
            f"- Current code scanning alerts: `{_int(code_scanning.get('current_alerts'))}`"
        )
        lines.append(f"- Stale code scanning alerts: `{_int(code_scanning.get('stale_alerts'))}`")
        unknown_count = _int(code_scanning.get("unknown_freshness_alerts"))
        if unknown_count:
            lines.append(f"- Unknown-freshness code scanning alerts: `{unknown_count}`")

        findings = [
            _as_dict(item)
            for item in _as_list(code_scanning.get("findings"))
            if isinstance(item, dict)
        ]
        for finding in findings[:5]:
            freshness = _string(finding.get("freshness") or "unknown")
            path = _string(finding.get("path") or "unknown")
            line = _string(finding.get("line"))
            location = f"{path}:{line}" if line else path
            rule_id = _string(finding.get("rule_id") or "unknown")
            severity = _string(finding.get("severity") or "unknown")
            action = _string(finding.get("recommended_action") or "review_alert_freshness")
            lines.append(
                f"- Code scanning {freshness} finding: `{location}` "
                f"(`{rule_id}`, severity=`{severity}`), action=`{action}`"
            )

    return lines


def _security_finding_diagnosis_lines(security_finding_diagnosis: JsonObject | None) -> list[str]:
    report = _as_dict(security_finding_diagnosis)
    if not report:
        return []

    summary = _as_dict(report.get("summary"))
    boundary = _as_dict(report.get("decision_boundary"))
    trusted_history = _as_dict(report.get(TRUSTED_REVIEWED_DISPOSITION_HISTORY))
    lines = [
        f"- Collection status: `{_string(report.get('collection_status') or 'unknown')}`",
        f"- Open findings: `{_int(summary.get('open_findings'))}`",
        f"- Current findings: `{_int(summary.get('current_findings'))}`",
        f"- Stale findings: `{_int(summary.get('stale_findings'))}`",
        (
            "- Metadata false-positive candidates: "
            f"`{_int(summary.get('scanner_metadata_false_positive_candidates'))}`"
        ),
        (
            "- Test-fixture candidates: "
            f"`{_int(summary.get('intentional_test_fixture_candidates'))}`"
        ),
        (f"- Mechanical fix proposals: `{_int(summary.get('safe_mechanical_fix_candidates'))}`"),
        f"- True-positive fixes required: `{_int(summary.get('true_positive_fix_required'))}`",
        (
            "- Trusted reviewed disposition context: "
            f"`{_string(trusted_history.get('status') or 'not_collected')}`"
        ),
        (
            "- Current findings with verified prior review context: "
            f"`{_int(trusted_history.get('matched_current_findings'))}`"
        ),
        (
            "- Historical disposition authorizes current action: "
            f"`{str(bool(boundary.get(HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION, False))).lower()}`"
        ),
        (
            "- Automatic security fix allowed: "
            f"`{str(bool(boundary.get(AUTOMATIC_SECURITY_FIX_ALLOWED, False))).lower()}`"
        ),
        (
            "- Automatic dismissal allowed: "
            f"`{str(bool(boundary.get(AUTOMATIC_DISMISSAL_ALLOWED, False))).lower()}`"
        ),
    ]

    findings = [_as_dict(item) for item in _as_list(report.get("diagnoses")) if _as_dict(item)]
    if not findings:
        lines.append("- Findings: none")
        return lines

    lines.append("- Findings:")
    for finding in findings[:5]:
        path = _string(finding.get("path") or "unknown")
        line = _string(finding.get("line"))
        location = f"{path}:{line}" if line else path
        rule_id = _string(finding.get("rule_id") or "unknown")
        tool = _string(finding.get("tool") or "unknown")
        freshness = _string(finding.get("freshness") or "unknown")
        classification = _string(finding.get("classification") or "unknown")
        action = _string(finding.get("recommended_action") or "review_current_finding")
        lines.append(
            f"  - `{rule_id}` at `{location}`: tool=`{tool}`, "
            f"freshness=`{freshness}`, classification=`{classification}`, action=`{action}`"
        )
        proposal = _string(finding.get("fix_proposal"))
        if proposal:
            lines.append(f"    - Proposal: {proposal}")
        disposition_context = _as_dict(finding.get(TRUSTED_REVIEWED_DISPOSITION_CONTEXT))
        matched_prior = _int(disposition_context.get(MATCHING_REVIEWED_DISPOSITION_COUNT))
        if matched_prior:
            lines.append(f"    - Verified prior reviewed dispositions: `{matched_prior}`")
            reason = _string(disposition_context.get("latest_reviewed_reason") or "unknown")
            lines.append(f"    - Latest prior reviewed reason: `{reason}`")
            lines.append(
                "    - Prior disposition is advisory evidence only; current action remains manual."
            )
        lines.append(
            "    - Human review required: "
            f"`{str(bool(finding.get('human_review_required', True))).lower()}`"
        )

    remaining = len(findings) - 5
    if remaining > 0:
        lines.append(f"  - ... `{remaining}` more")

    return lines


def _artifact_evidence_lines(payload: JsonObject, *, prefix: str = "  - ") -> list[str]:
    evidence = _as_dict(payload.get(ARTIFACT_EVIDENCE_KEY))
    if not evidence:
        return []

    status = _string(evidence.get("status") or "unknown")
    source = _string(evidence.get("source") or "unknown")
    expected = [
        _string(item) for item in _as_list(evidence.get("expected_artifacts")) if _string(item)
    ]
    present = [
        _string(item) for item in _as_list(evidence.get("present_artifacts")) if _string(item)
    ]
    missing = [
        _string(item) for item in _as_list(evidence.get("missing_artifacts")) if _string(item)
    ]

    lines = [f"{prefix}Artifact evidence: `{status}`"]
    if expected:
        lines.append(
            f"{prefix}Expected artifacts: " + ", ".join(f"`{item}`" for item in expected[:5])
        )
    if present:
        lines.append(
            f"{prefix}Present artifacts: " + ", ".join(f"`{item}`" for item in present[:5])
        )
    if missing:
        lines.append(
            f"{prefix}Missing artifacts: " + ", ".join(f"`{item}`" for item in missing[:5])
        )
    lines.append(f"{prefix}Artifact evidence source: `{source}`")
    lines.append(f"{prefix}Artifact evidence reporting only: `true`")
    lines.append(f"{prefix}Artifact automation allowed: `false`")
    return lines


def _job_step_confirmation_lines(payload: JsonObject, *, prefix: str = "  - ") -> list[str]:
    confirmation = _as_dict(payload.get(JOB_STEP_CONFIRMATION_KEY))
    if not confirmation:
        return []

    status = _string(confirmation.get("status") or "unknown")
    source = _string(confirmation.get("source") or "unknown")
    name = _string(confirmation.get("job_step_name"))
    conclusion = _string(confirmation.get("job_step_conclusion") or "unknown")
    lines = [f"{prefix}Job step confirmation: `{status}`"]
    if name:
        lines.append(f"{prefix}GitHub job step: `{name}`")
    lines.append(f"{prefix}GitHub job step conclusion: `{conclusion}`")
    lines.append(f"{prefix}Job step source: `{source}`")
    lines.append(f"{prefix}Job step reporting only: `true`")
    lines.append(f"{prefix}Job step automation allowed: `false`")
    return lines


def _failed_step_evidence_lines(payload: JsonObject, *, prefix: str = "  - ") -> list[str]:
    step = _as_dict(payload.get(FAILED_STEP_EVIDENCE_KEY))
    if not step:
        return []

    status = _string(step.get("status") or "unknown")
    command = _string(step.get("command"))
    source = _string(step.get("source") or "unknown")
    line_number = _int(step.get("line_number"))
    failure_line_number = _int(step.get("failure_line_number"))

    lines = [f"{prefix}Failed step evidence: `{status}`"]
    if command:
        lines.append(f"{prefix}Failed command: `{command}`")
    if line_number or failure_line_number:
        location = f"command line {line_number or 'unknown'}, failure line {failure_line_number or 'unknown'}"
        lines.append(f"{prefix}Failed step location: `{location}`")
    lines.append(f"{prefix}Failed step source: `{source}`")
    lines.append(f"{prefix}Failed step reporting only: `true`")
    lines.append(f"{prefix}Failed step automation allowed: `false`")
    lines.extend(_job_step_confirmation_lines(payload, prefix=prefix))
    return lines


def _failed_check_lines(check_intelligence: JsonObject) -> list[str]:
    failed = [_as_dict(item) for item in _as_list(check_intelligence.get("failed_checks"))]
    if not failed:
        return ["- none"]

    lines: list[str] = []
    for item in failed[:5]:
        diagnosis = _as_dict(item.get("diagnosis"))
        name = _string(item.get("name"))
        code = _string(diagnosis.get("code") or "unknown")
        title = _string(diagnosis.get("title") or "Unknown failure")
        safe = str(bool(item.get("safe_to_auto_fix", False))).lower()
        lines.append(f"- `{name}` -> {title} (`{code}`), safe_to_auto_fix=`{safe}`")
        first_failure = _as_dict(item.get("first_failure"))
        first_line = _string(first_failure.get("line"))
        if first_line:
            line_number = _int(first_failure.get("line_number"))
            tool = _string(first_failure.get("tool") or "unknown")
            kind = _string(first_failure.get("kind") or "unknown")
            location = f"line {line_number}" if line_number else "line unknown"
            lines.append(f"  - First failure: `{first_line}`")
            lines.append(f"  - Failure location: `{location}`")
            lines.append(f"  - Failure tool/kind: `{tool}` / `{kind}`")
        lines.extend(_failed_step_evidence_lines(item))
        lines.extend(_artifact_evidence_lines(item))
        safe_remediation = _as_dict(item.get("safe_remediation"))
        if bool(safe_remediation.get("safe_to_auto_fix", False)):
            strategy = _string(safe_remediation.get("strategy") or "unknown")
            reason = _string(safe_remediation.get("reason") or "approved safe remediation")
            lines.append(f"  - Safe remediation: `{strategy}`")
            lines.append(f"  - Safe reason: `{reason}`")
        formatter_files = [
            _string(path) for path in _as_list(item.get("formatter_changed_files")) if _string(path)
        ]
        if formatter_files:
            lines.append(
                "  - Formatter changed files: "
                + ", ".join(f"`{path}`" for path in formatter_files[:8])
            )
        if bool(item.get("stale_evidence", False)):
            head_sha = _string(item.get("head_sha") or "unknown")
            current_sha = _string(item.get("current_pr_head_sha") or "unknown")
            lines.append(f"  - Evidence freshness: `stale` (`{head_sha}` != `{current_sha}`)")
        outside_files = [
            _string(path) for path in _as_list(item.get("outside_changed_files")) if _string(path)
        ]
        if outside_files:
            lines.append(
                "  - Outside PR changed set: "
                + ", ".join(f"`{path}`" for path in outside_files[:8])
            )
        if bool(item.get("possible_changed_files_gate_fallout", False)):
            lines.append("  - Gate fallout: possible changed-files base-resolution issue")
    return lines


def _primary_blocker_lines(primary: JsonObject) -> list[str]:
    if not primary:
        return ["- none"]

    lines = [
        f"- Check/source: `{primary.get('check', '')}`",
        f"- Title: {primary.get('title', '')}",
        f"- Surface: `{primary.get('surface', '')}`",
        f"- Code: `{primary.get('code', '')}`",
    ]

    path = _string(primary.get("path"))
    line = _string(primary.get("line"))
    if path:
        location = f"{path}:{line}" if line else path
        lines.append(f"- File: `{location}`")

    url = _string(primary.get("url"))
    if url:
        lines.append(f"- URL: {url}")
    first_failure = _as_dict(primary.get("first_failure"))
    first_line = _string(primary.get("first_failure_line") or first_failure.get("line"))
    if first_line:
        line_number = _int(first_failure.get("line_number"))
        tool = _string(first_failure.get("tool") or "unknown")
        kind = _string(first_failure.get("kind") or "unknown")
        location = f"line {line_number}" if line_number else "line unknown"
        lines.append(f"- First failure: `{first_line}`")
        lines.append(f"- Failure location: `{location}`")
        lines.append(f"- Failure tool/kind: `{tool}` / `{kind}`")
    lines.extend(_failed_step_evidence_lines(primary, prefix="- "))
    lines.extend(_artifact_evidence_lines(primary, prefix="- "))
    safe_remediation = _as_dict(primary.get("safe_remediation"))
    if bool(safe_remediation.get("safe_to_auto_fix", False)):
        strategy = _string(safe_remediation.get("strategy") or "unknown")
        reason = _string(safe_remediation.get("reason") or "approved safe remediation")
        lines.append(f"- Safe remediation: `{strategy}`")
        lines.append(f"- Safe reason: `{reason}`")

    formatter_files = [
        _string(path) for path in _as_list(primary.get("formatter_changed_files")) if _string(path)
    ]
    if formatter_files:
        lines.append(
            "- Formatter changed files: " + ", ".join(f"`{path}`" for path in formatter_files[:8])
        )

    if bool(primary.get("review_first", False)):
        lines.append("- Review first: `true`")

    if bool(primary.get("stale_evidence", False)):
        head_sha = _string(primary.get("head_sha") or "unknown")
        current_sha = _string(primary.get("current_pr_head_sha") or "unknown")
        lines.append(f"- Evidence freshness: `stale` (`{head_sha}` != `{current_sha}`)")

    outside_files = [
        _string(path) for path in _as_list(primary.get("outside_changed_files")) if _string(path)
    ]
    if outside_files:
        lines.append(
            "- Outside PR changed set: " + ", ".join(f"`{path}`" for path in outside_files[:8])
        )

    if bool(primary.get("possible_changed_files_gate_fallout", False)):
        lines.append("- Gate fallout: possible changed-files base-resolution issue")

    lines.extend(_dependency_audit_lines(primary))

    impact = _string(primary.get("impact"))
    if impact:
        lines.append(f"- Impact: {impact}")

    return lines


def _dependency_audit_lines(primary: JsonObject) -> list[str]:
    audit = _as_dict(primary.get("dependency_audit"))
    if not audit:
        return []

    lines = ["", "Dependency audit evidence"]
    vulnerability_count = _int(audit.get("vulnerability_count"))
    package_count = _int(audit.get("package_count"))
    if vulnerability_count or package_count:
        lines.append(f"- Vulnerabilities: {vulnerability_count}")
        lines.append(f"- Packages: {package_count}")

    command = _string(audit.get("command"))
    if command:
        lines.append(f"- Command: `{command}`")

    report_path = _string(audit.get("report_path"))
    if report_path:
        lines.append(f"- Report: `{report_path}`")

    artifact_url = _string(audit.get("artifact_url"))
    if artifact_url:
        lines.append(f"- Artifact: {artifact_url}")

    ignored = [str(item) for item in _as_list(audit.get("ignored_vulnerabilities"))]
    if ignored:
        lines.append(f"- Ignored vulnerabilities: {', '.join(ignored)}")

    owner_files = [str(item) for item in _as_list(primary.get("owner_files"))]
    if owner_files:
        lines.append("- Owner files:")
        lines.extend(f"  - `{item}`" for item in owner_files)

    return lines


def _automation_lines(action_report: JsonObject) -> list[str]:
    automation = _as_dict(action_report.get("automation"))
    return [
        f"- Attempted: `{str(bool(automation.get('attempted', False))).lower()}`",
        f"- Allowed: `{str(bool(automation.get('allowed', False))).lower()}`",
        f"- Reason: {automation.get('reason', '')}",
    ]


def _bullet_lines(values: list[Any], *, none_text: str = "none") -> list[str]:
    items = [str(item) for item in values if isinstance(item, str) and item.strip()]
    return [f"- {item}" for item in items] or [f"- {none_text}"]


def _command_lines(values: list[Any]) -> list[str]:
    items = [str(item) for item in values if isinstance(item, str) and item.strip()]
    return [f"- `{item}`" for item in items] or ["- none"]


def _has_operator_content(lines: list[str]) -> bool:
    return any(line.strip() and line.strip() != "- none" for line in lines)


def _details_block(title: str, lines: list[str], *, open_by_default: bool = False) -> list[str]:
    marker = " open" if open_by_default else ""
    return [
        f"<details{marker}>",
        f"<summary><strong>{title}</strong></summary>",
        "",
        *lines,
        "",
        "</details>",
    ]


def _operator_section(
    title: str,
    lines: list[str],
    *,
    open_when: bool = False,
) -> list[str]:
    return _details_block(
        title,
        lines,
        open_by_default=open_when and _has_operator_content(lines),
    )


def _runtime_proof_artifact_lines(runtime_proof_artifacts: JsonObject | None) -> list[str]:
    summary = _as_dict(runtime_proof_artifacts)
    if not summary:
        return []

    isolated = _as_dict(summary.get("isolated_proof"))
    benchmark = _as_dict(summary.get("live_benchmark"))
    memory = _as_dict(summary.get("repo_memory"))
    trusted_history = _as_dict(summary.get(TRUSTED_HISTORY))
    trusted_signal_history = _as_dict(summary.get(TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY))
    boundary = _as_dict(summary.get("decision_boundary"))

    lines = [
        f"- Collection status: `{_string(summary.get('status') or 'not_collected')}`",
        f"- Isolated proof status: `{_string(isolated.get('status') or 'not_collected')}`",
        (
            "- Git inventory verified: "
            f"`{str(bool(isolated.get('git_inventory_verified', False))).lower()}`"
        ),
        (
            "- Runtime guard checked: "
            f"`{str(bool(isolated.get('runtime_guard_checked', False))).lower()}`"
        ),
        (
            "- Runtime guard passed: "
            f"`{str(bool(isolated.get('runtime_guard_passed', False))).lower()}`"
        ),
        f"- Runtime guard violations: `{_int(isolated.get('runtime_guard_violation_count'))}`",
        (
            "- Network boundary status: "
            f"`{_string(isolated.get('network_boundary_status') or 'not_collected')}`"
        ),
        (
            "- Network isolation enforced: "
            f"`{str(bool(isolated.get('network_isolation_enforced', False))).lower()}`"
        ),
        f"- Profiles executed: `{_int(isolated.get('profiles_executed'))}`",
        f"- Profiles blocked: `{_int(isolated.get('profiles_blocked'))}`",
        (
            "- Live benchmark collection status: "
            f"`{_string(benchmark.get('collection_status') or 'not_collected')}`"
        ),
        f"- Live benchmark status: `{_string(benchmark.get('status') or 'not_collected')}`",
    ]

    if benchmark.get("collection_status") == "collected":
        lines.extend(
            [
                f"- Live benchmark scenarios: `{_int(benchmark.get('scenario_count'))}`",
                f"- Live benchmark passed: `{_int(benchmark.get('passed_count'))}`",
                (
                    "- Live Git inventory verified scenarios: "
                    f"`{_int(benchmark.get('git_inventory_verified_count'))}`"
                ),
                (
                    "- Live expected failed-evidence scenarios: "
                    f"`{_int(benchmark.get('expected_failed_evidence_count'))}`"
                ),
                (
                    "- Live network boundary blocked scenarios: "
                    f"`{_int(benchmark.get('network_boundary_blocked_count'))}`"
                ),
                (
                    "- Live anti-cheat rejection scenarios: "
                    f"`{_int(benchmark.get('anti_cheat_rejection_count'))}`"
                ),
                (
                    "- Live network isolation enforced scenarios: "
                    f"`{_int(benchmark.get('network_isolation_enforced_count'))}`"
                ),
                (
                    "- Live benchmark boundary preserved: "
                    f"`{str(bool(benchmark.get('boundary_preserved', False))).lower()}`"
                ),
            ]
        )

    lines.extend(
        [
            (
                "- RepoMemory collection status: "
                f"`{_string(memory.get('collection_status') or 'not_collected')}`"
            ),
            f"- RepoMemory status: `{_string(memory.get('status') or 'not_collected')}`",
        ]
    )

    if memory.get("collection_status") == "collected":
        lines.extend(
            [
                (
                    "- RepoMemory live contract proven: "
                    f"`{str(bool(memory.get('live_contract_proven', False))).lower()}`"
                ),
                (
                    "- RepoMemory known safe candidates: "
                    f"`{_int(memory.get('known_safe_candidate_count'))}`"
                ),
                (
                    "- RepoMemory live safe candidates: "
                    f"`{_int(memory.get('live_safe_candidate_count'))}`"
                ),
                (
                    "- RepoMemory anti-cheat rejection scenarios: "
                    f"`{_int(memory.get('anti_cheat_rejection_scenario_count'))}`"
                ),
            ]
        )

    lines.extend(
        [
            (
                "- Trusted history collection status: "
                f"`{_string(trusted_history.get('collection_status') or 'not_collected')}`"
            ),
            (
                "- Trusted history status: "
                f"`{_string(trusted_history.get('status') or 'not_collected')}`"
            ),
        ]
    )

    if trusted_history.get("collection_status") == "collected":
        lines.extend(
            [
                (
                    "- Trusted history source workflow: "
                    f"`{_string(trusted_history.get('source_workflow'))}`"
                ),
                (
                    "- Trusted history latest accepted main head: "
                    f"`{_string(trusted_history.get('latest_accepted_main_head'))}`"
                ),
                (
                    "- Trusted history base ancestry verified: "
                    f"`{str(bool(trusted_history.get(BASE_ANCESTRY_VERIFIED, False))).lower()}`"
                ),
                (f"- Trusted history records: `{_int(trusted_history.get('record_count'))}`"),
                (
                    "- Trusted history live-contract-proven records: "
                    f"`{_int(trusted_history.get(LIVE_PROVEN_RECORD_COUNT))}`"
                ),
                (
                    "- Trusted history prior input read-only: "
                    f"`{str(bool(trusted_history.get(PRIOR_HISTORY_READ_ONLY_INPUT, False))).lower()}`"
                ),
                (
                    "- Trusted history controlled validation records: "
                    f"`{_int(trusted_history.get(CONTROLLED_VALIDATION_RECORD_COUNT))}`"
                ),
                (
                    "- Trusted history controlled validation scenarios: "
                    f"`{_int(trusted_history.get(CONTROLLED_VALIDATION_SCENARIO_COUNT))}`"
                ),
                (
                    "- Trusted history controlled structurally verified scenarios: "
                    f"`{_int(trusted_history.get(CONTROLLED_STRUCTURALLY_VERIFIED_COUNT))}`"
                ),
                (
                    "- Trusted history controlled review-first scenarios: "
                    f"`{_int(trusted_history.get(CONTROLLED_REVIEW_FIRST_COUNT))}`"
                ),
                (
                    "- Trusted history latest controlled validation status: "
                    f"`{_string(trusted_history.get('latest_controlled_validation_status') or 'not_collected')}`"
                ),
                (
                    "- Trusted history controlled validation reporting only: "
                    f"`{str(bool(trusted_history.get('controlled_validation_reporting_only', False))).lower()}`"
                ),
                (
                    "- Trusted history controlled validation authorizes current action: "
                    f"`{str(bool(trusted_history.get('controlled_validation_authorizes_current_action', False))).lower()}`"
                ),
                (
                    "- Trusted history producer-vetted registry collection status: "
                    f"`{_string(trusted_history.get(FLAKY_TEST_REGISTRY_COLLECTION_STATUS) or 'not_collected')}`"
                ),
                (
                    "- Trusted history producer-vetted registry status: "
                    f"`{_string(trusted_history.get(FLAKY_TEST_REGISTRY_STATUS) or 'not_collected')}`"
                ),
                (
                    "- Trusted history producer-vetted registry aggregate entries: "
                    f"`{_int(trusted_history.get(FLAKY_TEST_REGISTRY_ENTRY_COUNT))}`"
                ),
                (
                    "- Trusted history producer-vetted registry observation status: "
                    f"`{_string(trusted_history.get(FLAKY_TEST_REGISTRY_OBSERVATION_STATUS) or 'not_collected')}`"
                ),
                (
                    "- Trusted history producer-vetted observations collected: "
                    f"`{str(bool(trusted_history.get(FLAKY_TEST_REGISTRY_OBSERVATIONS_COLLECTED, False))).lower()}`"
                ),
                (
                    "- Trusted history producer-vetted registry producer vetted: "
                    f"`{str(bool(trusted_history.get(FLAKY_TEST_REGISTRY_PRODUCER_VETTED, False))).lower()}`"
                ),
                (
                    "- Trusted history producer-vetted registry raw test identity emitted: "
                    f"`{str(bool(trusted_history.get(FLAKY_TEST_REGISTRY_RAW_TEST_IDENTITY_EMITTED, False))).lower()}`"
                ),
                (
                    "- Trusted history producer-vetted registry current PR decision input: "
                    f"`{str(bool(trusted_history.get(FLAKY_TEST_REGISTRY_CURRENT_PR_DECISION_INPUT, False))).lower()}`"
                ),
                (
                    "- Automation allowed by trusted history: "
                    f"`{str(bool(trusted_history.get('automation_allowed', False))).lower()}`"
                ),
                (
                    "- Merge authorized by trusted history: "
                    f"`{str(bool(trusted_history.get('merge_authorized', False))).lower()}`"
                ),
                (
                    "- Semantic equivalence proven by trusted history: "
                    f"`{str(bool(trusted_history.get('semantic_equivalence_proven', False))).lower()}`"
                ),
            ]
        )

    lines.extend(
        [
            (
                "- Trusted diagnostic signal snapshot history collection status: "
                f"`{_string(trusted_signal_history.get('collection_status') or 'not_collected')}`"
            ),
            (
                "- Trusted diagnostic signal snapshot history status: "
                f"`{_string(trusted_signal_history.get('status') or 'not_collected')}`"
            ),
        ]
    )

    if trusted_signal_history.get("collection_status") == "collected":
        lines.extend(
            [
                (
                    "- Trusted diagnostic signal snapshot history source workflow: "
                    f"`{_string(trusted_signal_history.get('source_workflow'))}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history latest accepted main head: "
                    f"`{_string(trusted_signal_history.get('latest_accepted_main_head'))}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history base ancestry verified: "
                    f"`{str(bool(trusted_signal_history.get(BASE_ANCESTRY_VERIFIED, False))).lower()}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history records: "
                    f"`{_int(trusted_signal_history.get('record_count'))}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history quiet-green records: "
                    f"`{_int(trusted_signal_history.get('quiet_green_advisory_baseline_record_count'))}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history review-signal records: "
                    f"`{_int(trusted_signal_history.get('review_signal_record_count'))}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history integration-proof records: "
                    f"`{_int(trusted_signal_history.get('integration_proof_signal_record_count'))}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history latest snapshot status: "
                    f"`{_string(trusted_signal_history.get('latest_snapshot_status') or 'not_collected')}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history latest primary signal kind: "
                    f"`{_string(trusted_signal_history.get('latest_primary_signal_kind') or 'unknown')}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history advisor false-positive rate status: "
                    f"`{_string(trusted_signal_history.get('advisor_false_positive_rate_status') or 'unknown')}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history prior input read-only: "
                    f"`{str(bool(trusted_signal_history.get(PRIOR_HISTORY_READ_ONLY_INPUT, False))).lower()}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history reporting only: "
                    f"`{str(bool(trusted_signal_history.get('reporting_only', False))).lower()}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history current PR decision input: "
                    f"`{str(bool(trusted_signal_history.get('current_pr_decision_input', False))).lower()}`"
                ),
                (
                    "- Trusted diagnostic signal snapshot history feeds RepoMemory: "
                    f"`{str(bool(trusted_signal_history.get('feeds_repo_memory', False))).lower()}`"
                ),
                (
                    "- Automation allowed by trusted diagnostic signal snapshot history: "
                    f"`{str(bool(trusted_signal_history.get('automation_allowed', False))).lower()}`"
                ),
                (
                    "- Merge authorized by trusted diagnostic signal snapshot history: "
                    f"`{str(bool(trusted_signal_history.get('merge_authorized', False))).lower()}`"
                ),
                (
                    "- Semantic equivalence proven by trusted diagnostic signal snapshot history: "
                    f"`{str(bool(trusted_signal_history.get('semantic_equivalence_proven', False))).lower()}`"
                ),
                (
                    "- Historical snapshot authorizes current action: "
                    f"`{str(bool(trusted_signal_history.get('historical_snapshot_authorizes_current_action', False))).lower()}`"
                ),
            ]
        )

    lines.extend(
        [
            (
                "- Proof commands executed by renderer: "
                f"`{str(bool(boundary.get('proof_commands_executed_by_renderer', False))).lower()}`"
            ),
            (
                "- Automation allowed by runtime artifacts: "
                f"`{str(bool(boundary.get('automation_allowed', False))).lower()}`"
            ),
            (
                "- Merge authorized by runtime artifacts: "
                f"`{str(bool(boundary.get('merge_authorized', False))).lower()}`"
            ),
            (
                "- Semantic equivalence proven by runtime artifacts: "
                f"`{str(bool(boundary.get('semantic_equivalence_proven', False))).lower()}`"
            ),
        ]
    )
    return lines


def _trajectory_summary(records: list[JsonObject] | None) -> JsonObject:
    rows = [_as_dict(item) for item in records or [] if _as_dict(item)]
    return {
        "record_count": len(rows),
        "review_first_count": sum(
            1 for row in rows if _as_dict(row.get("decision")).get("review_first") is True
        ),
        "auto_fix_allowed_count": sum(
            1 for row in rows if _as_dict(row.get("decision")).get("auto_fix_allowed") is True
        ),
    }


def _trajectory_lines(records: list[JsonObject] | None) -> list[str]:
    rows = [_as_dict(item) for item in records or [] if _as_dict(item)]
    summary = _trajectory_summary(rows)
    if not summary["record_count"]:
        return []

    final_result_counts: dict[str, int] = {}
    for row in rows:
        final_result = _string(row.get("final_result") or "unknown")
        final_result_counts[final_result] = final_result_counts.get(final_result, 0) + 1

    lines = [
        f"- Records: `{summary['record_count']}`",
        f"- Review-first decisions: `{summary['review_first_count']}`",
        f"- Auto-fix allowed decisions: `{summary['auto_fix_allowed_count']}`",
    ]

    if final_result_counts:
        rendered_counts = ", ".join(
            f"`{name}`={count}" for name, count in sorted(final_result_counts.items())
        )
        lines.append(f"- Final results: {rendered_counts}")

    lines.append("- Decisions:")
    for row in rows[:5]:
        decision = _as_dict(row.get("decision"))
        diagnosis = _as_dict(row.get("diagnosis"))
        diagnostic_id = _string(row.get("diagnostic_id") or row.get("diagnosis_id") or "unknown")
        action = _string(row.get("action") or "unknown")
        failure_class = _string(diagnosis.get("failure_class") or "unknown")
        final_result = _string(row.get("final_result") or "unknown")
        review_first = str(bool(decision.get("review_first", False))).lower()
        auto_fix_allowed = str(bool(decision.get("auto_fix_allowed", False))).lower()
        lines.append(
            f"  - `{diagnostic_id}`: action=`{action}`, "
            f"class=`{failure_class}`, review_first=`{review_first}`, "
            f"auto_fix_allowed=`{auto_fix_allowed}`, result=`{final_result}`"
        )

    remaining = len(rows) - 5
    if remaining > 0:
        lines.append(f"  - ... `{remaining}` more")

    return lines


def _required_count(items: list[Any]) -> int:
    return sum(1 for item in items if bool(_as_dict(item).get("required", False)))


def _cleared_security_review_lines(
    *,
    check_intelligence: JsonObject,
    action_report: JsonObject,
    evidence_narrative: JsonObject,
    evidence_review_required: bool,
) -> list[str]:
    if not evidence_review_required:
        return []

    primary = _as_dict(evidence_narrative.get("primary_signal"))
    graph = _as_dict(evidence_narrative.get("graph"))
    top_blocker = _as_dict(graph.get("top_blocker"))
    surface = _string(primary.get("surface") or top_blocker.get("surface") or "")

    if surface != "security":
        return []

    security = _as_dict(
        check_intelligence.get("security_review")
        or _as_dict(action_report.get("evidence")).get("security_review")
    )
    if security.get("collected") is not True:
        return []

    if _int(security.get("unresolved_findings")) != 0:
        return []

    failed = _as_list(check_intelligence.get("failed_checks"))
    queued = _as_list(check_intelligence.get("queued_checks"))
    startup = _as_list(check_intelligence.get("startup_failures"))
    missing_required = _as_list(check_intelligence.get("missing_required_contexts"))

    if failed or missing_required or _required_count(queued) or _required_count(startup):
        return []

    return [
        "- Proof signal: `present`",
        "- Surface: `security`",
        "- Title: Security review cleared for changed code",
        "- Review signal reconciliation: `latest security review has no unresolved PR-owned findings`",
        "- Failed checks: `0`",
        "- Unresolved security findings: `0`",
        "- Security review action: `no fix or dismissal required for PR-owned security findings`",
    ]


def _security_review_real_diagnosis_lines(
    *,
    check_intelligence: JsonObject,
    action_report: JsonObject,
    evidence_narrative: JsonObject,
    security_finding_diagnosis: JsonObject | None,
    review_required: bool,
) -> list[str]:
    if not review_required:
        return []

    primary = _as_dict(evidence_narrative.get("primary_signal"))
    graph = _as_dict(evidence_narrative.get("graph"))
    top_blocker = _as_dict(graph.get("top_blocker"))
    surface = _string(primary.get("surface") or top_blocker.get("surface") or "")
    if surface != "security":
        return []

    report = _as_dict(security_finding_diagnosis)
    summary = _as_dict(report.get("summary"))
    code_scanning = _as_dict(
        check_intelligence.get("code_scanning_review")
        or _as_dict(action_report.get("evidence")).get("code_scanning_review")
    )
    security = _as_dict(
        check_intelligence.get("security_review")
        or _as_dict(action_report.get("evidence")).get("security_review")
    )

    current_count = _int(summary.get(CURRENT_FINDINGS))
    stale_count = _int(summary.get(STALE_FINDINGS))
    true_positive_count = _int(summary.get(TRUE_POSITIVE_FIX_REQUIRED))
    if not report:
        current_count = _int(code_scanning.get(CURRENT_ALERTS))
        stale_count = _int(code_scanning.get(STALE_ALERTS))
    if current_count == 0 and stale_count == 0:
        current_count = _int(security.get(UNRESOLVED_FINDINGS))

    if current_count == 0 and stale_count == 0:
        return []

    action = _string(top_blocker.get("action") or "")
    proof_commands = [
        str(item)
        for item in _as_list(evidence_narrative.get("next_proof"))
        if isinstance(item, str) and item.strip()
    ]

    lines = [
        "- Review signal: `present`",
        "- Surface: `security`",
        "- Checks status: `no failed required check reported by this diagnosis`",
        f"- Current findings: `{current_count}`",
        f"- Stale findings: `{stale_count}`",
        f"- True-positive fixes required: `{true_positive_count}`",
    ]
    if action:
        lines.append(f"- Operator action: `{action}`")

    boundary = _as_dict(report.get("decision_boundary"))
    lines.extend(
        _evidence_review_clarity_lines(
            quality_ok=_as_dict(evidence_narrative.get("quality")).get("ok") is True,
            surface="security",
        )
    )

    if current_count:
        lines.extend(
            [
                "- Diagnosis: current PR-owned security findings still need human disposition.",
                "- Merge impact: blocked until the current findings are fixed or reviewed as false positives.",
                "- Security review action: fix the current PR-owned finding or record a reviewed false-positive disposition.",
            ]
        )
    else:
        lines.extend(
            [
                "- Diagnosis: stale Code Scanning comments remain, but no current PR-head finding was reported.",
                "- Merge impact: refresh pending only; this is not an active current-head security blocker.",
                "- Security review action: wait for Code Scanning/GHAS refresh and rerun PR Quality; do not patch or dismiss stale alerts.",
            ]
        )

    lines.extend(
        [
            "- Automation boundary: no auto-remediation, auto-dismissal, or merge authorization claimed.",
            (
                "- Automatic dismissal allowed: "
                f"`{str(bool(boundary.get(AUTOMATIC_DISMISSAL_ALLOWED, False))).lower()}`"
            ),
            (
                "- Automatic security fix allowed: "
                f"`{str(bool(boundary.get(AUTOMATIC_SECURITY_FIX_ALLOWED, False))).lower()}`"
            ),
        ]
    )

    if proof_commands:
        lines.append("- Next proof:")
        lines.extend(f"  - `{command}`" for command in proof_commands[:5])

    findings = [_as_dict(item) for item in _as_list(report.get("diagnoses")) if _as_dict(item)]
    if not findings:
        findings = [
            _as_dict(item)
            for item in _as_list(code_scanning.get("findings"))
            if isinstance(item, dict)
        ]
    if findings:
        lines.append("- Finding sample:")
        for finding in findings[:4]:
            path = _string(finding.get("path") or "unknown")
            line = _string(finding.get("line"))
            location = f"{path}:{line}" if line else path
            freshness = _string(finding.get("freshness") or "unknown")
            classification = _string(finding.get("classification") or "unknown")
            action = _string(
                finding.get("recommended_action")
                or finding.get("action")
                or "manual_security_review"
            )
            rule_id = _string(finding.get("rule_id") or "unknown")
            lines.append(
                f"  - `{rule_id}` at `{location}`: freshness=`{freshness}`, "
                f"classification=`{classification}`, action=`{action}`"
            )

    return lines


def _reconciled_evidence_signal(
    *,
    check_intelligence: JsonObject,
    action_report: JsonObject,
    evidence_narrative: JsonObject,
    heading: str,
    lines: list[str],
    review_required: bool,
    security_finding_diagnosis: JsonObject | None = None,
) -> tuple[str, list[str], bool]:
    security_diagnosis = _security_review_real_diagnosis_lines(
        check_intelligence=check_intelligence,
        action_report=action_report,
        evidence_narrative=evidence_narrative,
        security_finding_diagnosis=security_finding_diagnosis,
        review_required=review_required,
    )
    if security_diagnosis:
        return "Evidence review signal", security_diagnosis, True

    cleared_security = _cleared_security_review_lines(
        check_intelligence=check_intelligence,
        action_report=action_report,
        evidence_narrative=evidence_narrative,
        evidence_review_required=review_required,
    )
    if cleared_security:
        return "Evidence proof signal", cleared_security, False

    return heading, lines, review_required


def _evidence_signal(evidence_narrative: JsonObject) -> tuple[str, list[str], bool]:
    primary = _as_dict(evidence_narrative.get("primary_signal"))
    graph = _as_dict(evidence_narrative.get("graph"))
    top_blocker = _as_dict(graph.get("top_blocker"))

    kind = _string(primary.get("kind") or "")
    title = _string(primary.get("title") or top_blocker.get("title") or "")
    surface = _string(primary.get("surface") or top_blocker.get("surface") or "unknown")
    action = _string(top_blocker.get("action") or "")
    top_title = _string(top_blocker.get("title") or "")
    top_surface = _string(top_blocker.get("surface") or "")
    review_first_count = _int(graph.get("review_first_count"))
    critical_count = _int(graph.get("critical_count"))
    top_review_first = bool(top_blocker.get("review_first", False))

    has_narrative_signal = kind in {"review_signal", "integration_proof"}
    has_top_blocker = bool(top_title) and top_title != "none" and top_surface != "none"
    if not has_narrative_signal and not has_top_blocker:
        return "", [], False

    review_required = (
        review_first_count > 0 or critical_count > 0 or action == "review" or top_review_first
    )
    signal_label = "Review signal" if review_required else "Proof signal"

    lines = [
        f"- {signal_label}: `present`",
        f"- Surface: `{surface or 'unknown'}`",
        f"- Title: {title or top_title or 'Evidence graph finding'}",
        f"- Graph nodes: `{_int(graph.get('node_count'))}`",
        f"- Review-first nodes: `{review_first_count}`",
        f"- Critical nodes: `{critical_count}`",
    ]

    if action:
        lines.append(f"- Operator action: `{action}`")
    if isinstance(top_blocker.get("review_first"), bool):
        lines.append(f"- Review first: `{str(top_blocker.get('review_first')).lower()}`")

    if review_required:
        lines.extend(
            _evidence_review_clarity_lines(
                quality_ok=_as_dict(evidence_narrative.get("quality")).get("ok") is True,
                surface=surface or top_surface or "unknown",
            )
        )

    proof_commands = [
        str(item)
        for item in _as_list(evidence_narrative.get("next_proof"))
        if isinstance(item, str) and item.strip()
    ]
    if proof_commands:
        lines.extend(["- Next proof:"])
        lines.extend(f"  - `{command}`" for command in proof_commands[:5])

    heading = "Evidence review signal" if review_required else "Evidence proof signal"
    return heading, lines, review_required


def _evidence_review_clarity_lines(
    *,
    quality_ok: bool,
    surface: str,
) -> list[str]:
    if not quality_ok:
        return []

    lines = [
        "- Gate interpretation: `quality gate passed; evidence review still required`",
        "- Failure status: `not a failed quality gate and not a failed required check`",
        "- Merge impact: `human review required before merge`",
        "- Automation boundary: `no auto-remediation or security dismissal attempted`",
    ]

    if surface == "security":
        lines.append(
            "- Security review action: `fix the PR-owned security finding or dismiss the false positive with a review reason`"
        )
    else:
        lines.append(
            f"- Review action: `review the listed {surface or 'unknown'} evidence before merge`"
        )

    return lines


def _patch_plan_lines(evidence_narrative: JsonObject) -> list[str]:
    patch_plan = _as_dict(evidence_narrative.get("patch_plan"))
    if not patch_plan or not patch_plan.get("enabled"):
        return []

    lines = [
        f"- Status: `{_string(patch_plan.get('status') or 'unknown')}`",
        f"- Source kind: `{_string(patch_plan.get('source_kind') or 'unknown')}`",
        f"- Source code: `{_string(patch_plan.get('source_code') or 'UNKNOWN')}`",
        f"- Safe to auto-fix: `{str(bool(patch_plan.get('safe_to_auto_fix', False))).lower()}`",
        f"- Dry run only: `{str(bool(patch_plan.get('dry_run_only', True))).lower()}`",
        f"- Requires human review: `{str(bool(patch_plan.get('requires_human_review', True))).lower()}`",
        f"- Patch steps: `{int(patch_plan.get('patch_step_count', 0) or 0)}`",
    ]

    proof_commands = [
        str(command)
        for command in _as_list(patch_plan.get("proof_commands"))
        if isinstance(command, str) and command.strip()
    ]
    if proof_commands:
        lines.extend(["- Proof commands:"])
        lines.extend(f"  - `{command}`" for command in proof_commands[:5])

    review_commands = [
        str(command)
        for command in _as_list(patch_plan.get("recommended_commands"))
        if isinstance(command, str) and command.strip()
    ]
    if review_commands:
        lines.extend(["- Review commands:"])
        lines.extend(f"  - `{command}`" for command in review_commands[:5])

    return lines


def _operator_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _operator_safetygate_summary_lines(
    *,
    action_report: JsonObject,
    trajectory_records: list[JsonObject],
    runtime_proof_artifacts: JsonObject,
) -> list[str]:
    failure_bundle = _as_dict(action_report.get("failure_bundle"))
    failure_safety = _as_dict(failure_bundle.get("safety_summary"))

    patch_score = _as_dict(action_report.get("patch_score"))
    patch_decision = _as_dict(patch_score.get("decision"))
    patch_safety = _as_dict(patch_score.get("safety_gate_evidence"))
    patch_boundary = _as_dict(patch_safety.get("decision_boundary"))

    protected_verifier = _as_dict(action_report.get("protected_verifier_result"))
    verifier_decision = _as_dict(protected_verifier.get("decision"))
    verifier_safety = _as_dict(protected_verifier.get("safety_gate_evidence"))
    verifier_boundary = _as_dict(verifier_safety.get("decision_boundary"))
    verifier_repo_memory = _as_dict(protected_verifier.get("repo_memory_evidence"))
    verifier_contract = _as_dict(
        verifier_repo_memory.get("_".join(("failure", "vector", "contract", "evidence")))
    )
    verifier_contract_boundary = _as_dict(verifier_contract.get("decision_boundary"))
    verifier_runtime_proof = _as_dict(
        protected_verifier.get(PROTECTED_VERIFIER_RUNTIME_PROOF_EVIDENCE)
    )
    verifier_benchmark_contract = _as_dict(
        verifier_runtime_proof.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_REPLAY_EVIDENCE)
    )
    verifier_benchmark_contract_boundary = _as_dict(
        verifier_benchmark_contract.get("decision_boundary")
    )

    benchmark = _as_dict(action_report.get("benchmark_report"))
    benchmark_safety = _as_dict(benchmark.get("safety_gate_evidence"))
    benchmark_boundary = _as_dict(benchmark_safety.get("decision_boundary"))

    repo_memory = _as_dict(action_report.get("repo_memory"))
    memory_safety = _as_dict(repo_memory.get("safety_gate_evidence"))
    memory_boundary = _as_dict(memory_safety.get("decision_boundary"))

    runtime_boundary = _as_dict(runtime_proof_artifacts.get("decision_boundary"))

    trajectory_safety_records = [
        _as_dict(row.get("safety_gate"))
        for row in trajectory_records
        if _as_dict(row.get("safety_gate"))
    ]

    verifier_contract_automation_allowed = _operator_bool(
        verifier_contract_boundary.get("automation_allowed")
    )
    verifier_contract_patch_application_allowed = _operator_bool(
        verifier_contract_boundary.get("patch_application_allowed")
    )
    verifier_contract_security_dismissal_allowed = _operator_bool(
        verifier_contract_boundary.get("security_dismissal_allowed")
    )
    verifier_contract_merge_authorized = _operator_bool(
        verifier_contract_boundary.get("merge_authorized")
    )
    verifier_contract_semantic_equivalence_claim = _operator_bool(
        verifier_contract_boundary.get("semantic_equivalence_claim")
    )
    verifier_benchmark_contract_automation_allowed = _operator_bool(
        verifier_benchmark_contract_boundary.get("automation_allowed")
    )
    verifier_benchmark_contract_patch_application_allowed = _operator_bool(
        verifier_benchmark_contract_boundary.get("patch_application_allowed")
    )
    verifier_benchmark_contract_security_dismissal_allowed = _operator_bool(
        verifier_benchmark_contract_boundary.get("security_dismissal_allowed")
    )
    verifier_benchmark_contract_merge_authorized = _operator_bool(
        verifier_benchmark_contract_boundary.get("merge_authorized")
    )
    verifier_benchmark_contract_semantic_equivalence_claim = _operator_bool(
        verifier_benchmark_contract_boundary.get("semantic_equivalence_claim")
    )

    observed = any(
        [
            failure_safety,
            patch_score,
            protected_verifier,
            verifier_contract,
            verifier_benchmark_contract,
            benchmark_safety,
            memory_safety,
            trajectory_safety_records,
        ]
    )
    if not observed:
        return []

    automation_allowed = any(
        [
            _operator_bool(failure_safety.get("automation_allowed")),
            _operator_bool(patch_decision.get("automation_allowed")),
            _operator_bool(patch_boundary.get("automation_allowed")),
            _operator_bool(verifier_decision.get("automation_allowed")),
            _operator_bool(verifier_boundary.get("automation_allowed")),
            verifier_contract_automation_allowed,
            verifier_benchmark_contract_automation_allowed,
            _operator_bool(benchmark_boundary.get("automation_allowed")),
            _operator_bool(memory_boundary.get("automation_allowed")),
            _operator_bool(runtime_boundary.get("automation_allowed")),
            any(_operator_bool(row.get("automation_allowed")) for row in trajectory_safety_records),
        ]
    )
    patch_application_allowed = any(
        [
            _operator_bool(failure_safety.get("patch_application_allowed")),
            _operator_bool(patch_boundary.get("patch_application_allowed")),
            _operator_bool(verifier_boundary.get("patch_application_allowed")),
            verifier_contract_patch_application_allowed,
            verifier_benchmark_contract_patch_application_allowed,
            _operator_bool(benchmark_boundary.get("patch_application_allowed")),
            _operator_bool(memory_boundary.get("patch_application_allowed")),
            any(
                _operator_bool(row.get("patch_application_allowed"))
                for row in trajectory_safety_records
            ),
        ]
    )
    merge_authorized = any(
        [
            _operator_bool(failure_safety.get("merge_authorized")),
            _operator_bool(patch_decision.get("merge_authorized")),
            _operator_bool(patch_boundary.get("merge_authorized")),
            _operator_bool(verifier_decision.get("merge_authorized")),
            _operator_bool(verifier_boundary.get("merge_authorized")),
            verifier_contract_merge_authorized,
            verifier_benchmark_contract_merge_authorized,
            _operator_bool(benchmark_boundary.get("merge_authorized")),
            _operator_bool(memory_boundary.get("merge_authorized")),
            _operator_bool(runtime_boundary.get("merge_authorized")),
            any(_operator_bool(row.get("merge_authorized")) for row in trajectory_safety_records),
        ]
    )
    semantic_equivalence_proven = any(
        [
            _operator_bool(failure_safety.get("semantic_equivalence_proven")),
            _operator_bool(patch_decision.get("semantic_equivalence_proven")),
            _operator_bool(patch_boundary.get("semantic_equivalence_proven")),
            _operator_bool(verifier_decision.get("semantic_equivalence_proven")),
            _operator_bool(verifier_boundary.get("semantic_equivalence_proven")),
            _operator_bool(benchmark_boundary.get("semantic_equivalence_proven")),
            _operator_bool(memory_boundary.get("semantic_equivalence_proven")),
            _operator_bool(runtime_boundary.get("semantic_equivalence_proven")),
            any(
                _operator_bool(row.get("semantic_equivalence_proven"))
                for row in trajectory_safety_records
            ),
        ]
    )

    def _operator_unique_strings(*values: object) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            for item in _as_list(value):
                text = _string(item)
                if text and text not in seen:
                    seen.add(text)
                    result.append(text)
        return result

    verifier_benchmark_contract_expanded_authority_fields = _operator_unique_strings(
        verifier_benchmark_contract.get("expanded_authority_fields")
    )

    allowed_files = _operator_unique_strings(
        failure_safety.get("allowed_files"),
        patch_score.get("allowed_files"),
        patch_safety.get("allowed_files"),
        verifier_safety.get("allowed_files"),
        benchmark_safety.get("allowed_files"),
        memory_safety.get("allowed_files"),
        action_report.get("allowed_files"),
        [path for row in trajectory_safety_records for path in _as_list(row.get("allowed_files"))],
    )
    proof_commands = _operator_unique_strings(
        failure_safety.get("proof_commands"),
        patch_score.get("proof_requirements"),
        patch_safety.get("proof_commands"),
        verifier_safety.get("proof_commands"),
        benchmark_safety.get("proof_commands"),
        memory_safety.get("proof_commands"),
        runtime_proof_artifacts.get("proof_commands"),
        runtime_boundary.get("proof_commands"),
        action_report.get("proof_commands"),
        [
            command
            for row in trajectory_safety_records
            for command in _as_list(row.get("proof_commands"))
        ],
    )

    safetygate_authority_expanded = any(
        [
            failure_safety,
            patch_score,
            protected_verifier,
            verifier_benchmark_contract,
            benchmark_safety,
            memory_safety,
            trajectory_safety_records,
        ]
    ) and any(
        [
            automation_allowed
            and not verifier_contract_automation_allowed
            and not verifier_benchmark_contract_automation_allowed,
            patch_application_allowed
            and not verifier_contract_patch_application_allowed
            and not verifier_benchmark_contract_patch_application_allowed,
            merge_authorized
            and not verifier_contract_merge_authorized
            and not verifier_benchmark_contract_merge_authorized,
            semantic_equivalence_proven,
        ]
    )
    contract_authority_expanded = any(
        [
            verifier_contract_automation_allowed,
            verifier_contract_patch_application_allowed,
            verifier_contract_security_dismissal_allowed,
            verifier_contract_merge_authorized,
            verifier_contract_semantic_equivalence_claim,
        ]
    )
    benchmark_contract_authority_expanded = any(
        [
            verifier_benchmark_contract_automation_allowed,
            verifier_benchmark_contract_patch_application_allowed,
            verifier_benchmark_contract_security_dismissal_allowed,
            verifier_benchmark_contract_merge_authorized,
            verifier_benchmark_contract_semantic_equivalence_claim,
            verifier_benchmark_contract_expanded_authority_fields,
        ]
    )

    if contract_authority_expanded:
        next_action = "Review-first: ProtectedVerifier RepoMemory contract evidence attempted to expand authority."
    elif benchmark_contract_authority_expanded:
        next_action = "Review-first: ProtectedVerifier benchmark replay contract evidence attempted to expand authority."
    elif safetygate_authority_expanded:
        next_action = "Review-first: a SafetyGate boundary attempted to expand authority."
    else:
        next_action = (
            "Human review may use this evidence, but no automation or merge authority is granted."
        )

    return [
        "- Failure bundle review-first: "
        f"`{str(_operator_bool(failure_safety.get('review_first'))).lower()}`",
        "- Failure bundle safe-fix allowed: "
        f"`{str(_operator_bool(failure_safety.get('safe_fix_allowed'))).lower()}`",
        "- Operator summary allowed files: "
        f"`{', '.join(allowed_files) if allowed_files else 'none'}`",
        "- Operator summary proof commands: "
        f"`{', '.join(proof_commands) if proof_commands else 'none'}`",
        f"- Trajectory SafetyGate records: `{len(trajectory_safety_records)}`",
        f"- RepoMemory SafetyGate records: `{_int(memory_safety.get('record_count'))}`",
        "- Replay benchmark SafetyGate scenarios: "
        f"`{_int(benchmark_safety.get('scenario_count'))}`",
        f"- PatchScorer status: `{_string(patch_decision.get('status')) or 'not_collected'}`",
        f"- PatchScorer score: `{_int(patch_score.get('score'))}`",
        "- ProtectedVerifier status: "
        f"`{_string(verifier_decision.get('status')) or 'not_collected'}`",
        "- ProtectedVerifier RepoMemory FailureVector contract records: "
        f"`{_int(verifier_contract.get('record_count'))}`",
        "- ProtectedVerifier RepoMemory contract security-relevant records: "
        f"`{_int(verifier_contract.get('security_relevance_count'))}`",
        "- ProtectedVerifier RepoMemory contract authority preserved records: "
        f"`{_int(verifier_contract.get('authority_boundary_preserved_count'))}`",
        "- ProtectedVerifier RepoMemory contract patch application allowed: "
        f"`{str(verifier_contract_patch_application_allowed).lower()}`",
        "- ProtectedVerifier RepoMemory contract security dismissal allowed: "
        f"`{str(verifier_contract_security_dismissal_allowed).lower()}`",
        "- ProtectedVerifier RepoMemory contract merge authorized: "
        f"`{str(verifier_contract_merge_authorized).lower()}`",
        "- ProtectedVerifier RepoMemory contract semantic equivalence claim: "
        f"`{str(verifier_contract_semantic_equivalence_claim).lower()}`",
        "- ProtectedVerifier benchmark replay contract scenarios: "
        f"`{_int(verifier_benchmark_contract.get('scenario_count'))}`",
        "- ProtectedVerifier benchmark replay contract records: "
        f"`{_int(verifier_benchmark_contract.get('record_count'))}`",
        "- ProtectedVerifier benchmark replay contract security-relevant records: "
        f"`{_int(verifier_benchmark_contract.get('security_relevance_count'))}`",
        "- ProtectedVerifier benchmark replay contract authority preserved records: "
        f"`{_int(verifier_benchmark_contract.get('authority_boundary_preserved_count'))}`",
        "- ProtectedVerifier benchmark replay contract expanded authority fields: "
        f"`{', '.join(verifier_benchmark_contract_expanded_authority_fields) if verifier_benchmark_contract_expanded_authority_fields else 'none'}`",
        "- ProtectedVerifier benchmark replay contract patch application allowed: "
        f"`{str(verifier_benchmark_contract_patch_application_allowed).lower()}`",
        "- ProtectedVerifier benchmark replay contract security dismissal allowed: "
        f"`{str(verifier_benchmark_contract_security_dismissal_allowed).lower()}`",
        "- ProtectedVerifier benchmark replay contract merge authorized: "
        f"`{str(verifier_benchmark_contract_merge_authorized).lower()}`",
        "- ProtectedVerifier benchmark replay contract semantic equivalence claim: "
        f"`{str(verifier_benchmark_contract_semantic_equivalence_claim).lower()}`",
        f"- Operator next action: `{next_action}`",
        f"- Operator summary automation allowed: `{str(automation_allowed).lower()}`",
        f"- Operator summary patch application allowed: `{str(patch_application_allowed).lower()}`",
        f"- Operator summary merge authorized: `{str(merge_authorized).lower()}`",
        "- Operator summary semantic equivalence proven: "
        f"`{str(semantic_equivalence_proven).lower()}`",
    ]


def _review_model_scalar(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
    return str(value)


def _markdown_table_value(value: object) -> str:
    return _review_model_scalar(value).replace("|", "\\|")


def _review_model_artifact_index() -> list[JsonObject]:
    return [
        {
            "path": "index.html",
            "kind": "html",
            "surface": "artifact_center",
            "title": "Artifact landing page",
            "description": "Browser-ready entry point for the PR Quality artifact bundle.",
            "primary": True,
            "format": "html",
        },
        {
            "path": "pr-review-artifacts-manifest.json",
            "kind": "json",
            "surface": "artifact_manifest",
            "title": "Artifact manifest",
            "description": "Machine-readable manifest for expected PR Quality artifact bundle entries.",
            "primary": False,
            "format": "json",
        },
        {
            "path": "pr-review-dashboard.html",
            "kind": "html",
            "surface": "review_dashboard",
            "title": "Visual dashboard",
            "description": "Browser-ready visual dashboard with state, blocker, proof, and artifact cards.",
            "primary": False,
            "format": "html",
        },
        {
            "path": "pr-review-summary.md",
            "kind": "markdown",
            "surface": "review_summary",
            "title": "Compact summary",
            "description": "Concise human review panel used by the PR comment and step summary.",
            "primary": False,
            "format": "markdown",
        },
        {
            "path": "pr-review-model.json",
            "kind": "json",
            "surface": "review_model",
            "title": "Review model",
            "description": "Machine-readable source-of-truth model for all rendered review surfaces.",
            "primary": False,
            "format": "json",
        },
        {
            "path": "pr-comment-body.md",
            "kind": "markdown",
            "surface": "raw_evidence",
            "title": "Raw evidence body",
            "description": "Full diagnostic evidence retained for audit and debugging.",
            "primary": False,
            "format": "markdown",
        },
        {
            "path": "pr-quality-comment",
            "kind": "github_artifact",
            "surface": "artifact_bundle",
            "title": "Uploaded artifact bundle",
            "description": "GitHub Actions artifact bundle containing full diagnostic evidence.",
            "primary": False,
            "format": "github_artifact",
        },
    ]


def _authority_evidence_source_index() -> list[JsonObject]:
    return [
        {
            "path": "trajectory/trajectory.jsonl",
            "kind": "jsonl",
            "surface": "authority_evidence",
            "title": "Trajectory authority boundary records",
            "description": "Raw TrajectoryStore records carrying per-record authority_boundary evidence.",
            "primary": False,
            "format": "jsonl",
            "reporting_only": True,
            "authority_boundary": {
                "boundary_mode": "reporting_only",
                "patch_automation": False,
                "security_dismissal": False,
                "merge_authorization": False,
                "semantic_equivalence_claim": False,
            },
        },
        {
            "path": "trajectory-pattern-insights/pattern-insights.json",
            "kind": "json",
            "surface": "authority_evidence",
            "title": "Trajectory authority evidence rollup",
            "description": "PatternInsights rollup of observed trajectory authority boundary evidence.",
            "primary": False,
            "format": "json",
            "reporting_only": True,
            "authority_boundary": {
                "boundary_mode": "reporting_only",
                "patch_automation": False,
                "security_dismissal": False,
                "merge_authorization": False,
                "semantic_equivalence_claim": False,
            },
        },
        {
            "path": "repo-memory/repo-memory-profile.json",
            "kind": "json",
            "surface": "authority_evidence",
            "title": "RepoMemory trajectory authority evidence",
            "description": "RepoMemory profile containing trajectory_authority_evidence and denied authority fields.",
            "primary": False,
            "format": "json",
            "reporting_only": True,
            "authority_boundary": {
                "boundary_mode": "reporting_only",
                "patch_automation": False,
                "security_dismissal": False,
                "merge_authorization": False,
                "semantic_equivalence_claim": False,
            },
        },
        {
            "path": "runtime-proof/summary/runtime-proof-artifacts.json",
            "kind": "json",
            "surface": "authority_evidence",
            "title": "Runtime proof authority summary",
            "description": "Runtime-proof summary exposing RepoMemory trajectory authority status and counts.",
            "primary": False,
            "format": "json",
            "reporting_only": True,
            "authority_boundary": {
                "boundary_mode": "reporting_only",
                "patch_automation": False,
                "security_dismissal": False,
                "merge_authorization": False,
                "semantic_equivalence_claim": False,
            },
        },
        {
            "path": "runtime-proof/summary/runtime-proof-artifacts.md",
            "kind": "markdown",
            "surface": "authority_evidence",
            "title": "Runtime proof authority markdown",
            "description": "Human-readable runtime-proof authority evidence summary.",
            "primary": False,
            "format": "markdown",
            "reporting_only": True,
            "authority_boundary": {
                "boundary_mode": "reporting_only",
                "patch_automation": False,
                "security_dismissal": False,
                "merge_authorization": False,
                "semantic_equivalence_claim": False,
            },
        },
        {
            "path": "pr-comment-metadata.json",
            "kind": "json",
            "surface": "authority_evidence",
            "title": "PR comment authority metadata",
            "description": "Comment metadata carrying RepoMemory trajectory authority evidence into visibility verification.",
            "primary": False,
            "format": "json",
            "reporting_only": True,
            "authority_boundary": {
                "boundary_mode": "reporting_only",
                "patch_automation": False,
                "security_dismissal": False,
                "merge_authorization": False,
                "semantic_equivalence_claim": False,
            },
        },
    ]


def _workflow_permission_review_packet_from_sources(
    action_report: JsonObject,
    check_intelligence: JsonObject,
) -> JsonObject:
    candidate_sources = [
        _as_dict(action_report.get("workflow_governance_report")),
        _as_dict(check_intelligence.get("workflow_governance_report")),
        _as_dict(action_report.get("workflow_governance")),
        _as_dict(check_intelligence.get("workflow_governance")),
        _as_dict(action_report),
        _as_dict(check_intelligence),
    ]
    for source in candidate_sources:
        packet = _as_dict(source.get("permission_review_evidence_packet"))
        if packet:
            return packet
    return {}


def _workflow_permission_review_packet_markdown_lines(packet: JsonObject) -> list[str]:
    if not packet:
        return []

    lines = [
        "## Workflow permission review evidence",
        "",
        f"- Schema version: `{_string(packet.get('schema_version') or 'unknown')}`",
        f"- Status: `{_string(packet.get('status') or 'unknown')}`",
        f"- Permission review count: `{_int(packet.get('permission_review_count'))}`",
        f"- Next allowed action: `{_string(packet.get('next_allowed_action') or 'none')}`",
        f"- Review first: `{str(bool(packet.get('review_first', True))).lower()}`",
        f"- Safe to patch: `{str(bool(packet.get('safe_to_patch', False))).lower()}`",
        "- Automatic permission reduction allowed: "
        f"`{str(bool(packet.get('automatic_permission_reduction_allowed', False))).lower()}`",
    ]

    required = [
        _string(item) for item in _as_list(packet.get("required_human_evidence")) if _string(item)
    ]
    if required:
        lines.extend(["", "### Required human evidence", ""])
        lines.extend(f"- `{item}`" for item in required)

    blocked = [_string(item) for item in _as_list(packet.get("blocked_actions")) if _string(item)]
    if blocked:
        lines.extend(["", "### Blocked permission actions", ""])
        lines.extend(f"- `{item}`" for item in blocked)

    tasks = [_as_dict(item) for item in _as_list(packet.get("review_tasks"))]
    if tasks:
        lines.extend(["", "### Permission review task sample", ""])
        for task in tasks[:5]:
            lines.append(f"#### {_string(task.get('workflow') or 'unknown')}")
            lines.append(
                f"- Permission group: `{_string(task.get('permission_group') or 'unknown')}`"
            )
            lines.append("- Reviewer decision required: `true`")
            lines.append("- Requires human review: `true`")
            lines.append("- Safe to patch: `false`")
            scopes = [
                _string(item)
                for item in _as_list(task.get("granted_write_scopes"))
                if _string(item)
            ]
            if scopes:
                lines.append("- Granted write scopes:")
                lines.extend(f"  - `{scope}`" for scope in scopes)
            reasons = [
                _string(item)
                for item in _as_list(task.get("inferred_permission_reasons"))
                if _string(item)
            ]
            if reasons:
                lines.append("- Inferred permission reasons:")
                lines.extend(f"  - {reason}" for reason in reasons)
        if len(tasks) > 5:
            lines.append(f"- Additional permission review tasks: `{len(tasks) - 5}`")

    lines.extend(
        [
            "",
            "_Reporting-only. This PR Quality surface does not authorize workflow permission mutation, automatic permission reduction, patch automation, security dismissal, merge, or semantic-equivalence claims._",
        ]
    )
    return lines


def _workflow_permission_review_packet_html(packet: JsonObject) -> str:
    if not packet:
        return ""

    tasks = [_as_dict(item) for item in _as_list(packet.get("review_tasks"))]
    task_items = []
    for task in tasks[:6]:
        workflow = _html_escape(_string(task.get("workflow") or "unknown"))
        group = _html_escape(_string(task.get("permission_group") or "unknown"))
        scopes = ", ".join(
            _html_escape(_string(scope))
            for scope in _as_list(task.get("granted_write_scopes"))
            if _string(scope)
        )
        task_items.append(
            "<li>"
            f"<strong><code>{workflow}</code></strong>"
            f"<span>Group: <code>{group}</code></span>"
            f"<span>Scopes: <code>{scopes or 'none'}</code></span>"
            "</li>"
        )

    task_list = (
        "".join(task_items)
        if task_items
        else "<li><span>No permission review tasks reported.</span></li>"
    )

    rows = [
        ("Schema", packet.get("schema_version") or "unknown"),
        ("Status", packet.get("status") or "unknown"),
        ("Permission reviews", _int(packet.get("permission_review_count"))),
        ("Next allowed action", packet.get("next_allowed_action") or "none"),
        ("Review first", bool(packet.get("review_first", True))),
        ("Safe to patch", bool(packet.get("safe_to_patch", False))),
        (
            "Automatic permission reduction",
            bool(packet.get("automatic_permission_reduction_allowed", False)),
        ),
    ]
    table_html = "\n".join(
        f"<tr><th>{_html_escape(label)}</th><td><code>{_html_escape(value)}</code></td></tr>"
        for label, value in rows
    )

    return (
        '<section class="panel workflow-permission-evidence">'
        '<span class="section-kicker">Workflow governance</span>'
        "<h2>Workflow permission review evidence</h2>"
        "<p>Human-review packet for workflow permission findings. Reporting-only; does not authorize permission mutation.</p>"
        f"<table>{table_html}</table>"
        "<h3>Permission review tasks</h3>"
        f"<ul>{task_list}</ul>"
        '<p class="boundary">Reporting-only. No automatic permission reduction, patch automation, security dismissal, merge authorization, or semantic-equivalence claim.</p>'
        "</section>"
    )


def _review_model_failure_vector_signal(
    *,
    action_report: JsonObject,
    check_intelligence: JsonObject,
    evidence_narrative: JsonObject,
) -> JsonObject:
    graph = _as_dict(evidence_narrative.get("graph"))
    top_blocker = _as_dict(graph.get("top_blocker"))
    primary_blocker = _as_dict(action_report.get("primary_blocker"))

    diagnostic_vectors = _as_dict(
        check_intelligence.get("diagnostic_vectors") or action_report.get("diagnostic_vectors")
    )
    diagnostic_candidates = [
        _as_dict(item)
        for item in _as_list(diagnostic_vectors.get("failure_vectors"))
        if _as_dict(item)
    ]
    single_failure_vector = _as_dict(diagnostic_vectors.get("failure_vector"))
    if single_failure_vector:
        diagnostic_candidates.insert(0, single_failure_vector)

    candidates: list[tuple[str, JsonObject]] = []
    candidates.extend(("diagnostic_vector", item) for item in diagnostic_candidates)
    if top_blocker:
        candidates.append(("evidence_top_blocker", top_blocker))
    if primary_blocker:
        candidates.append(("primary_blocker", primary_blocker))
    candidates.extend(
        ("failed_check", _as_dict(item))
        for item in _as_list(check_intelligence.get("failed_checks"))
        if _as_dict(item)
    )

    for source, candidate in candidates:
        first_failure = _as_dict(candidate.get("first_failure"))
        failed_step = _as_dict(candidate.get(FAILED_STEP_EVIDENCE_KEY))
        safe_remediation = _as_dict(candidate.get("safe_remediation"))

        affected_files = [
            _string(item)
            for key in (
                "affected_files",
                "owner_files",
                "likely_owner_files",
                "formatter_changed_files",
            )
            for item in _as_list(candidate.get(key))
            if _string(item)
        ]
        explicit_path = _string(
            candidate.get("owner_hint")
            or candidate.get("failing_file")
            or candidate.get("path")
            or first_failure.get("path")
        )
        if explicit_path and explicit_path not in affected_files:
            affected_files.insert(0, explicit_path)

        headline_signal = _string(
            candidate.get("headline_signal")
            or candidate.get("headline_failure")
            or candidate.get("title")
            or candidate.get("name")
            or candidate.get("check")
            or candidate.get("context")
            or "unknown"
        )
        actual_failure = _string(
            candidate.get("actual_failure")
            or candidate.get("first_failure_line")
            or first_failure.get("line")
            or candidate.get("details")
            or candidate.get("message")
            or candidate.get("reason")
            or headline_signal
        )
        failure_type = _string(
            candidate.get("failure_type")
            or candidate.get("failure_class")
            or first_failure.get("kind")
            or candidate.get("code")
            or "unknown"
        )
        failing_command = _string(
            candidate.get("failing_command")
            or candidate.get("command")
            or failed_step.get("command")
            or "unknown"
        )
        failing_test_or_check = _string(
            candidate.get("failing_test_or_check")
            or candidate.get("failing_test")
            or candidate.get("check")
            or candidate.get("name")
            or first_failure.get("tool")
            or "unknown"
        )
        owner_hint = _string(
            candidate.get("owner_hint") or (affected_files[0] if affected_files else "")
        )

        if not any(
            value and value != "unknown"
            for value in (
                headline_signal,
                actual_failure,
                failure_type,
                failing_command,
                failing_test_or_check,
                owner_hint,
            )
        ):
            continue

        return {
            "source": source,
            "headline_signal": headline_signal,
            "actual_failure": actual_failure,
            "failure_type": failure_type,
            "failing_command": failing_command,
            "failing_test_or_check": failing_test_or_check,
            "exit_code": _int(
                candidate.get("exit_code")
                or candidate.get("status_code")
                or failed_step.get("exit_code")
            ),
            "owner_hint": owner_hint or "unknown",
            "affected_files": affected_files[:10],
            "safe_fix_candidate": bool(
                candidate.get("safe_fix_candidate")
                or candidate.get("safe_to_auto_fix")
                or safe_remediation.get("safe_to_auto_fix")
            ),
            "safe_fix_allowed": False,
            "reporting_only": True,
        }

    return {
        "source": "none",
        "headline_signal": "none",
        "actual_failure": "none",
        "failure_type": "none",
        "failing_command": "none",
        "failing_test_or_check": "none",
        "exit_code": 0,
        "owner_hint": "none",
        "affected_files": [],
        "safe_fix_candidate": False,
        "safe_fix_allowed": False,
        "reporting_only": True,
    }


def _review_model_ghas_blocker_details(
    *,
    action_report: JsonObject,
    check_intelligence: JsonObject,
) -> JsonObject:
    code_scanning = _as_dict(
        check_intelligence.get("code_scanning_review")
        or _as_dict(action_report.get("evidence")).get("code_scanning_review")
    )

    findings: list[JsonObject] = []
    for item in _as_list(code_scanning.get("findings")):
        finding = _as_dict(item)
        if not finding:
            continue

        path = _string(finding.get("path") or "unknown")
        line = _string(finding.get("line"))
        location = f"{path}:{line}" if line else path
        freshness = _string(finding.get("freshness") or "unknown")
        recommended_action = _string(finding.get("recommended_action") or "review_alert_freshness")

        if freshness == "current":
            proof_commands = [
                "python -m sdetkit security check --root . --format json",
                "python -m pre_commit run -a",
                "make proof-after-format",
            ]
        elif freshness == "stale":
            proof_commands = ["gh pr checks"]
        else:
            proof_commands = [
                "Review alert freshness against the current PR head SHA.",
                "gh pr checks",
            ]

        findings.append(
            {
                "number": _string(finding.get("number") or "unknown"),
                "url": _string(finding.get("url")),
                "rule_id": _string(finding.get("rule_id") or "unknown"),
                "severity": _string(finding.get("severity") or "unknown"),
                "path": path,
                "line": line,
                "location": location,
                "alert_commit_sha": _string(finding.get("commit_sha")),
                "current_head_sha": _string(finding.get("current_head_sha")),
                "freshness": freshness,
                "recommended_action": recommended_action,
                "message": _string(finding.get("message")),
                "dismissal_allowed": False,
                "dismissal_guidance": (
                    "_".join(["forbidden", "until", "human", "false", "positive", "review"])
                    if freshness == "current"
                    else "not_needed_for_stale_alert"
                ),
                "proof_commands": proof_commands,
            }
        )

    return {
        "schema_version": "sdetkit.pr_quality.ghas_blocker_details.v1",
        "collected": bool(code_scanning.get("collected", False)),
        "collection_status": _string(code_scanning.get("collection_status") or "unknown"),
        "collection_reason": _string(code_scanning.get("collection_reason")),
        "source": _string(code_scanning.get("source")),
        "open_alerts": _int(code_scanning.get("open_alerts")),
        "current_alerts": _int(code_scanning.get("current_alerts")),
        "stale_alerts": _int(code_scanning.get("stale_alerts")),
        "unknown_freshness_alerts": _int(code_scanning.get("unknown_freshness_alerts")),
        "current_head_sha": _string(code_scanning.get("current_head_sha")),
        "has_current_blockers": any(item.get("freshness") == "current" for item in findings),
        "dismissal_allowed": False,
        "reporting_only": True,
        "findings": findings[:10],
    }


def _canonical_review_state(
    *,
    source_status: str,
    failed_checks: int,
    required_queued_checks: int,
    required_startup_failures: int,
    missing_required_contexts: int,
    evidence_review_required: bool,
    stale_only_security_signal: bool,
) -> str:
    if stale_only_security_signal:
        return "stale"
    if source_status == "green" and (
        failed_checks > 0
        or required_queued_checks > 0
        or required_startup_failures > 0
        or missing_required_contexts > 0
    ):
        return "invalid"
    if required_queued_checks > 0 and failed_checks == 0 and required_startup_failures == 0:
        return "waiting"
    if (
        failed_checks > 0
        or required_startup_failures > 0
        or missing_required_contexts > 0
        or source_status
        in {
            "incomplete",
            "review_required",
            "safe_fix_available",
        }
    ):
        return "blocked"
    if source_status not in KNOWN_ACTION_REPORT_STATUSES:
        return "invalid"
    if evidence_review_required:
        return "review"
    return "ready"


def _canonical_review_decision(
    *,
    review_state: str,
    blocker_title: str,
    blocker_action: str,
) -> tuple[str, str, str]:
    if review_state == "waiting":
        return (
            "none",
            "wait_for_required_checks",
            "wait_for_required_checks",
        )
    if review_state == "blocked":
        return (
            blocker_title or "Required contributor proof is blocked",
            blocker_action or "resolve_primary_blocker",
            "do_not_merge_until_blocker_resolved",
        )
    if review_state == "review":
        return (
            "none",
            "review_listed_evidence",
            "human_review_required_before_merge",
        )
    if review_state == "ready":
        return (
            "none",
            "review_and_decide",
            "automated_proof_complete_human_decision_required",
        )
    if review_state == "stale":
        return (
            "Evidence is stale for the current PR head",
            WAIT_FOR_CODE_SCANNING_REFRESH,
            WAIT_FOR_CODE_SCANNING_REFRESH,
        )
    return (
        "PR Quality review evidence is internally inconsistent",
        "repair_review_evidence",
        "do_not_merge_until_review_model_repaired",
    )


def _review_model_fallback_action(
    *,
    status: str,
    action: str,
    evidence_review_required: bool,
    evidence_signal_lines: list[str],
    stale_only_security_signal: bool,
) -> str:
    if stale_only_security_signal:
        return WAIT_FOR_CODE_SCANNING_REFRESH
    if status != "green":
        return action or "review_primary_blocker"
    if evidence_review_required:
        return action or "review_listed_evidence"
    if evidence_signal_lines:
        return action or "rerun_listed_proof"
    return "none"


def build_pr_quality_review_model(
    *,
    status: str,
    evidence_signal_heading: str,
    evidence_signal_lines: list[str],
    evidence_review_required: bool,
    action_report: JsonObject,
    check_intelligence: JsonObject,
    evidence_narrative: JsonObject,
) -> JsonObject:
    primary_signal = _as_dict(evidence_narrative.get("primary_signal"))
    graph = _as_dict(evidence_narrative.get("graph"))
    top_blocker = _as_dict(graph.get("top_blocker"))
    primary_blocker = _as_dict(action_report.get("primary_blocker"))
    failure_vector_signal = _review_model_failure_vector_signal(
        action_report=action_report,
        check_intelligence=check_intelligence,
        evidence_narrative=evidence_narrative,
    )
    ghas_blocker_details = _review_model_ghas_blocker_details(
        action_report=action_report,
        check_intelligence=check_intelligence,
    )
    stale_only_security_signal = (
        _int(ghas_blocker_details.get("open_alerts")) > 0
        and _int(ghas_blocker_details.get("current_alerts")) == 0
        and _int(ghas_blocker_details.get("stale_alerts")) > 0
    )

    surface = _string(
        primary_signal.get("surface")
        or top_blocker.get("surface")
        or primary_blocker.get("surface")
        or "unknown"
    )
    title = _string(
        primary_signal.get("title")
        or top_blocker.get("title")
        or primary_blocker.get("title")
        or "none"
    )
    action = _string(
        top_blocker.get("action")
        or primary_blocker.get("action")
        or primary_blocker.get("code")
        or ""
    )

    fallback_action = _review_model_fallback_action(
        status=status,
        action=action,
        evidence_review_required=evidence_review_required,
        evidence_signal_lines=evidence_signal_lines,
        stale_only_security_signal=stale_only_security_signal,
    )

    cleared_security_signal = any(
        "Security review cleared for changed code" in line
        or "no fix or dismissal required for PR-owned security findings" in line
        for line in evidence_signal_lines
    )

    proof_commands: list[str] = []
    for index, line in enumerate(evidence_signal_lines):
        if line.strip() != "- Next proof:":
            continue
        for candidate in evidence_signal_lines[index + 1 :]:
            stripped = candidate.strip()
            if not stripped.startswith("- `"):
                break
            proof_commands.append(stripped.removeprefix("- `").removesuffix("`"))
        break

    if not proof_commands and not cleared_security_signal:
        proof_commands = [
            str(command)
            for command in _as_list(evidence_narrative.get("next_proof"))
            if isinstance(command, str) and command.strip()
        ]
    if not proof_commands and not cleared_security_signal:
        proof_commands = [
            str(command)
            for command in _as_list(action_report.get("proof_commands"))
            if isinstance(command, str) and command.strip()
        ]

    def _check_labels(items: object) -> list[str]:
        labels: list[str] = []
        for item in _as_list(items):
            check = _as_dict(item)
            label = _string(
                check.get("name")
                or check.get("context")
                or check.get("check")
                or check.get("workflow")
                or check.get("title")
                or item
            )
            if label:
                labels.append(label)
        return labels

    failed_check_names = _check_labels(check_intelligence.get("failed_checks"))
    required_queued_check_names = _check_labels(
        [
            item
            for item in _as_list(check_intelligence.get("queued_checks"))
            if bool(_as_dict(item).get("required", False))
        ]
    )
    required_startup_failure_names = _check_labels(
        [
            item
            for item in _as_list(check_intelligence.get("startup_failures"))
            if bool(_as_dict(item).get("required", False))
        ]
    )
    missing_required_context_names = [
        _string(item)
        for item in _as_list(check_intelligence.get("missing_required_contexts"))
        if _string(item)
    ]
    failed_count = len(failed_check_names)
    required_queued = len(required_queued_check_names)
    required_startup = len(required_startup_failure_names)
    missing_required = len(missing_required_context_names)

    recommended_actions = [
        str(item)
        for item in _as_list(action_report.get("recommended_actions"))
        if isinstance(item, str) and item.strip()
    ]

    primary_title = _string(primary_blocker.get("title") or title)
    primary_surface = _string(primary_blocker.get("surface") or surface)
    primary_action = _string(primary_blocker.get("action") or action or fallback_action)
    primary_code = _string(primary_blocker.get("code"))
    primary_details = _string(
        primary_blocker.get("details")
        or primary_blocker.get("message")
        or primary_blocker.get("reason")
    )

    if stale_only_security_signal:
        stale_only_actions = [
            "Wait for Code Scanning/GHAS refresh; no current code-scanning alert matches the PR head SHA.",
            "Do not patch or dismiss stale alerts unless a refreshed alert matches the current PR head.",
            "Re-run PR Quality after Code Scanning refreshes.",
        ]
        recommended_actions = stale_only_actions
        proof_commands = ["gh pr checks"]
        cleared_security_signal = True
        primary_title = "Code Scanning refresh pending"
        primary_surface = "security"
        primary_action = WAIT_FOR_CODE_SCANNING_REFRESH
        primary_code = STALE_ONLY_CODE_SCANNING
        primary_details = (
            "No current Code Scanning alert matches the PR head SHA; "
            "stale alerts are refresh-pending evidence only."
        )
        failure_vector_signal = {
            "source": STALE_ONLY_CODE_SCANNING,
            "headline_signal": primary_title,
            "actual_failure": "No current Code Scanning alert matches the PR head SHA.",
            "failure_type": STALE_ONLY_SECURITY_SIGNAL,
            "failing_command": "none",
            "failing_test_or_check": "none",
            "exit_code": 0,
            "owner_hint": "none",
            "affected_files": [],
            "safe_fix_candidate": False,
            "safe_fix_allowed": False,
            "reporting_only": True,
        }

    review_state = _canonical_review_state(
        source_status=status,
        failed_checks=failed_count,
        required_queued_checks=required_queued,
        required_startup_failures=required_startup,
        missing_required_contexts=missing_required,
        evidence_review_required=evidence_review_required,
        stale_only_security_signal=stale_only_security_signal,
    )
    canonical_blocker, next_action, merge_assessment = _canonical_review_decision(
        review_state=review_state,
        blocker_title=primary_title,
        blocker_action=primary_action,
    )

    return {
        "schema_version": "sdetkit.pr_quality.review_model.v2",
        "schema": {
            "name": "sdetkit.pr_quality.review_model",
            "version": 2,
            "previous_version": "sdetkit.pr_quality.review_model.v1",
            "compatibility": "additive",
            "decision_logic": "canonical_review_state_v1",
            "authority_boundary": "reporting_only",
        },
        "generated_by": "sdetkit.pr_quality_action_report",
        "artifact_index": _review_model_artifact_index(),
        "workflow_permission_review_evidence_packet": _workflow_permission_review_packet_from_sources(
            action_report,
            check_intelligence,
        ),
        "primary_blocker": {
            "title": primary_title,
            "surface": primary_surface,
            "action": primary_action,
            "code": primary_code,
            "path": _string(primary_blocker.get("path")),
            "details": primary_details,
        },
        "recommended_actions": recommended_actions[:10],
        "failure_vector_signal": failure_vector_signal,
        "ghas_blocker_details": ghas_blocker_details,
        "failed_check_names": failed_check_names,
        "required_queued_check_names": required_queued_check_names,
        "required_startup_failure_names": required_startup_failure_names,
        "missing_required_context_names": missing_required_context_names,
        "decision": {
            "review_state": review_state,
            "status": status,
            "source_status": status,
            "state_consistent": review_state != "invalid",
            "primary_blocker": canonical_blocker,
            "merge_assessment": merge_assessment,
            "next_action": next_action,
            "risk_surface": surface,
            "signal_title": title,
            "comment_signal": _string(evidence_signal_heading or "none"),
            "review_first_evidence": evidence_review_required,
            "failed_checks": failed_count,
            "required_queued_checks": required_queued,
            "required_startup_failures": required_startup,
            "missing_required_contexts": missing_required,
            "cleared_security_signal": cleared_security_signal,
            STALE_ONLY_SECURITY_SIGNAL: stale_only_security_signal,
        },
        "proof_to_rerun": proof_commands[:5],
        "authority_boundary": {
            "boundary_mode": "reporting_only",
            "patch_automation": False,
            "security_dismissal": False,
            "merge_authorization": False,
            "semantic_equivalence_claim": False,
        },
    }


def _reviewer_dashboard_lines(
    *,
    status: str,
    evidence_signal_heading: str,
    evidence_signal_lines: list[str],
    evidence_review_required: bool,
    action_report: JsonObject,
    check_intelligence: JsonObject,
    evidence_narrative: JsonObject,
) -> list[str]:
    model = build_pr_quality_review_model(
        status=status,
        evidence_signal_heading=evidence_signal_heading,
        evidence_signal_lines=evidence_signal_lines,
        evidence_review_required=evidence_review_required,
        action_report=action_report,
        check_intelligence=check_intelligence,
        evidence_narrative=evidence_narrative,
    )
    decision = _normalized_review_decision(model)
    authority = _as_dict(model.get("authority_boundary"))
    proof_commands = [
        str(command)
        for command in _as_list(model.get("proof_to_rerun"))
        if isinstance(command, str) and command.strip()
    ]

    lines = [
        "### Decision",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Review state | `{_review_model_state(model)}` |",
        f"| Source status | `{_review_model_scalar(decision.get('source_status') or decision.get('status'))}` |",
        f"| Merge assessment | `{_review_model_scalar(decision.get('merge_assessment'))}` |",
        f"| Next reviewer action | `{_review_model_scalar(decision.get('next_action'))}` |",
        f"| Changed risk surface | `{_markdown_table_value(decision.get('risk_surface'))}` |",
        f"| Signal title | {_markdown_table_value(decision.get('signal_title'))} |",
        f"| Comment signal | `{_markdown_table_value(decision.get('comment_signal'))}` |",
        f"| Review-first evidence | `{str(bool(decision.get('review_first_evidence'))).lower()}` |",
        f"| Failed checks | `{_review_model_scalar(decision.get('failed_checks'))}` |",
        f"| Required queued checks | `{_review_model_scalar(decision.get('required_queued_checks'))}` |",
        f"| Required startup failures | `{_review_model_scalar(decision.get('required_startup_failures'))}` |",
        f"| Missing required contexts | `{_review_model_scalar(decision.get('missing_required_contexts'))}` |",
        "",
        "### Proof to rerun",
        "",
    ]

    if proof_commands:
        lines.append("```bash")
        lines.extend(proof_commands)
        lines.append("```")
    else:
        lines.append("`none`")

    lines.extend(
        [
            "",
            "### Authority boundary",
            "",
            "| Authority | Value |",
            "|---|---|",
            f"| Boundary mode | `{_string(authority.get('boundary_mode'))}` |",
            f"| Patch automation | `{str(bool(authority.get('patch_automation'))).lower()}` |",
            f"| Security dismissal | `{str(bool(authority.get('security_dismissal'))).lower()}` |",
            f"| Merge authorization | `{str(bool(authority.get('merge_authorization'))).lower()}` |",
            f"| Semantic equivalence claim | `{str(bool(authority.get('semantic_equivalence_claim'))).lower()}` |",
        ]
    )

    return lines


def _review_model_state(model: JsonObject) -> str:
    decision = _as_dict(model.get("decision"))
    canonical = _review_model_scalar(decision.get("review_state"))
    if canonical in CANONICAL_REVIEW_STATES:
        return canonical

    status = _review_model_scalar(decision.get("status") or "unknown")
    failed_total = _int(decision.get("failed_checks"))
    queued_total = _int(decision.get("required_queued_checks"))
    startup_total = _int(decision.get("required_startup_failures"))
    missing_total = _int(decision.get("missing_required_contexts"))
    review_first = bool(decision.get("review_first_evidence"))
    stale_only_security_signal = bool(decision.get(STALE_ONLY_SECURITY_SIGNAL))

    return _canonical_review_state(
        source_status=status,
        failed_checks=failed_total,
        required_queued_checks=queued_total,
        required_startup_failures=startup_total,
        missing_required_contexts=missing_total,
        evidence_review_required=review_first,
        stale_only_security_signal=stale_only_security_signal,
    )


def _review_model_state_class(review_state: str) -> str:
    if review_state == "ready":
        return "status-green"
    if review_state in {"waiting", "review", "stale"}:
        return "status-review"
    return "status-failed"


def _review_model_state_label(review_state: str) -> str:
    return {
        "waiting": "waiting for CI",
        "blocked": "blocked",
        "review": "human review required",
        "ready": "ready for human decision",
        "stale": "stale evidence",
        "invalid": "invalid evidence",
    }.get(review_state, review_state.replace("_", " "))


def _normalized_review_decision(model: JsonObject) -> JsonObject:
    decision = dict(_as_dict(model.get("decision")))
    review_state = _review_model_state(model)
    source_status = _review_model_scalar(
        decision.get("source_status") or decision.get("status") or "unknown"
    )
    primary_blocker = _as_dict(model.get("primary_blocker"))
    blocker_title = _review_model_scalar(
        decision.get("primary_blocker") or primary_blocker.get("title") or ""
    )
    blocker_action = _review_model_scalar(
        primary_blocker.get("action") or decision.get("next_action") or ""
    )
    (
        canonical_blocker,
        canonical_action,
        canonical_merge_assessment,
    ) = _canonical_review_decision(
        review_state=review_state,
        blocker_title=blocker_title,
        blocker_action=blocker_action,
    )

    decision.update(
        {
            "review_state": review_state,
            "status": source_status,
            "source_status": source_status,
            "state_consistent": review_state != "invalid",
            "primary_blocker": canonical_blocker,
            "merge_assessment": canonical_merge_assessment,
            "next_action": canonical_action,
        }
    )
    return decision


def _contributor_review_panel_rows(
    model: JsonObject,
) -> list[tuple[str, object]]:
    decision = _normalized_review_decision(model)
    ghas_details = _as_dict(model.get("ghas_blocker_details"))

    required_counts = [
        ("failed", _int(decision.get("failed_checks"))),
        ("queued", _int(decision.get("required_queued_checks"))),
        ("startup", _int(decision.get("required_startup_failures"))),
        ("missing", _int(decision.get("missing_required_contexts"))),
    ]
    required_parts = [f"{count} {label}" for label, count in required_counts if count > 0]
    required_summary = "; ".join(required_parts) if required_parts else "clear"

    collected = bool(ghas_details.get("collected", False))
    current_alerts = _int(ghas_details.get("current_alerts"))
    stale_alerts = _int(ghas_details.get("stale_alerts"))
    if not collected:
        security_summary = "unavailable"
    elif current_alerts > 0:
        security_summary = f"{current_alerts} current alert(s)"
    elif stale_alerts > 0:
        security_summary = f"clear for current head; {stale_alerts} stale alert(s)"
    else:
        security_summary = "clear"

    return [
        ("Review state", _review_model_state(model)),
        (
            "First blocker",
            _review_model_scalar(decision.get("primary_blocker") or "none"),
        ),
        (
            "Next action",
            _review_model_scalar(decision.get("next_action") or "none"),
        ),
        ("Required checks", required_summary),
        ("Security posture", security_summary),
        (
            "Merge posture",
            _review_model_scalar(decision.get("merge_assessment") or "unknown"),
        ),
    ]


def render_pr_quality_review_summary(model: JsonObject) -> str:
    decision = _normalized_review_decision(model)
    authority = _as_dict(model.get("authority_boundary"))
    failure_vector_signal = _as_dict(model.get("failure_vector_signal"))
    ghas_blocker_details = _as_dict(model.get("ghas_blocker_details"))
    proof_commands = [
        str(command)
        for command in _as_list(model.get("proof_to_rerun"))
        if isinstance(command, str) and command.strip()
    ]
    recommended_actions = [
        str(item)
        for item in _as_list(model.get("recommended_actions"))
        if isinstance(item, str) and item.strip()
    ]
    failed_check_names = [
        str(item)
        for item in _as_list(model.get("failed_check_names"))
        if isinstance(item, str) and item.strip()
    ]
    queued_check_names = [
        str(item)
        for item in _as_list(model.get("required_queued_check_names"))
        if isinstance(item, str) and item.strip()
    ]
    startup_failure_names = [
        str(item)
        for item in _as_list(model.get("required_startup_failure_names"))
        if isinstance(item, str) and item.strip()
    ]
    missing_context_names = [
        str(item)
        for item in _as_list(model.get("missing_required_context_names"))
        if isinstance(item, str) and item.strip()
    ]

    def _count(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _joined(items: list[str]) -> str:
        return ", ".join(items) if items else "none"

    def _markdown_table(rows: list[tuple[str, object]]) -> list[str]:
        rendered = ["| Item | Value |", "|---|---|"]
        for label, value in rows:
            rendered.append(f"| {label} | `{_markdown_table_value(value)}` |")
        return rendered

    def _details(summary: str, body: list[str], *, open_by_default: bool = False) -> list[str]:
        attr = " open" if open_by_default else ""
        return [
            f"<details{attr}>",
            f"<summary>{summary}</summary>",
            "",
            *body,
            "",
            "</details>",
        ]

    failed_total = _count(decision.get("failed_checks"))
    queued_total = _count(decision.get("required_queued_checks"))
    startup_total = _count(decision.get("required_startup_failures"))
    missing_total = _count(decision.get("missing_required_contexts"))
    stale_only_security_signal = bool(decision.get(STALE_ONLY_SECURITY_SIGNAL))
    review_state = _review_model_state(model)
    first_action = _review_model_scalar(decision.get("next_action") or "none")

    failure_actual = _review_model_scalar(failure_vector_signal.get("actual_failure") or "none")
    failure_source = _review_model_scalar(failure_vector_signal.get("source") or "none")
    failure_owner = _review_model_scalar(failure_vector_signal.get("owner_hint") or "none")
    failure_type = _review_model_scalar(failure_vector_signal.get("failure_type") or "none")
    failing_command = _review_model_scalar(failure_vector_signal.get("failing_command") or "none")
    failing_test = _review_model_scalar(
        failure_vector_signal.get("failing_test_or_check") or "none"
    )
    affected_files = [
        str(item)
        for item in _as_list(failure_vector_signal.get("affected_files"))
        if isinstance(item, str) and item.strip()
    ]

    active_blocker_open = review_state in {
        "blocked",
        "review",
        "stale",
        "invalid",
    }
    failure_vector_open = active_blocker_open and failure_actual not in {"", "none"}
    proof_open = active_blocker_open and bool(proof_commands)
    ghas_findings = [
        _as_dict(item) for item in _as_list(ghas_blocker_details.get("findings")) if _as_dict(item)
    ]
    ghas_open = bool(ghas_findings) and (active_blocker_open or stale_only_security_signal)

    lines = [
        "# PR Quality Review Summary",
        "",
        "## Contributor decision",
        "",
        *_markdown_table(_contributor_review_panel_rows(model)),
        "",
    ]

    if recommended_actions:
        lines.extend(["## Recommended actions", ""])
        lines.extend(f"- {action}" for action in recommended_actions[:10])
        lines.append("")

    lines.extend(["## Adaptive review details", ""])

    blocker_body = [
        "| Item | Value |",
        "|---|---|",
        f"| Merge assessment | `{_review_model_scalar(decision.get('merge_assessment'))}` |",
        f"| Next action | `{_review_model_scalar(decision.get('next_action'))}` |",
        f"| Risk surface | `{_markdown_table_value(decision.get('risk_surface'))}` |",
        f"| Signal title | `{_markdown_table_value(decision.get('signal_title'))}` |",
        f"| Signal | `{_markdown_table_value(decision.get('comment_signal'))}` |",
        f"| Review-first evidence | `{_review_model_scalar(decision.get('review_first_evidence'))}` |",
        f"| Cleared security signal | `{_review_model_scalar(decision.get('cleared_security_signal'))}` |",
        f"| Stale-only security signal | `{str(stale_only_security_signal).lower()}` |",
        "",
    ]
    blocker_body.extend(
        [
            "### Canonical next action",
            "",
            f"- `{first_action}`",
        ]
    )
    additional_guidance = [
        action for action in recommended_actions if action and action != first_action
    ]
    if additional_guidance:
        blocker_body.extend(["", "### Additional guidance", ""])
        blocker_body.extend(f"- {action}" for action in additional_guidance[:5])

    decision_detail_title = {
        "waiting": "⏳ Waiting for required checks",
        "blocked": "🚨 Active blocker / decision details",
        "review": "👀 Human review required",
        "ready": "✅ Ready for human decision",
        "stale": "🟡 Stale evidence / refresh required",
        "invalid": "❌ Invalid review evidence",
    }.get(review_state, "Decision details")

    lines.extend(
        _details(
            decision_detail_title,
            blocker_body,
            open_by_default=active_blocker_open,
        )
    )
    lines.append("")

    failure_body = [
        "| Failure field | Value |",
        "|---|---|",
        f"| Source | `{_markdown_table_value(failure_source)}` |",
        f"| Actual failure | `{_markdown_table_value(failure_actual)}` |",
        f"| Failure type | `{_markdown_table_value(failure_type)}` |",
        f"| Failing command | `{_markdown_table_value(failing_command)}` |",
        f"| Failing test/check | `{_markdown_table_value(failing_test)}` |",
        f"| Owner hint | `{_markdown_table_value(failure_owner)}` |",
        f"| Safe-fix candidate | `{_review_model_scalar(failure_vector_signal.get('safe_fix_candidate'))}` |",
        f"| Safe-fix allowed | `{_review_model_scalar(failure_vector_signal.get('safe_fix_allowed'))}` |",
        f"| Reporting only | `{_review_model_scalar(failure_vector_signal.get('reporting_only'))}` |",
    ]
    if affected_files:
        failure_body.extend(["", "### Affected files", ""])
        failure_body.extend(f"- `{item}`" for item in affected_files[:10])

    lines.extend(
        _details(
            "🧭 Failure vector deep dive",
            failure_body,
            open_by_default=failure_vector_open,
        )
    )
    lines.append("")

    ghas_body = [
        "| Item | Value |",
        "|---|---|",
        f"| Collected | `{_review_model_scalar(ghas_blocker_details.get('collected'))}` |",
        f"| Collection status | `{_markdown_table_value(ghas_blocker_details.get('collection_status') or 'unknown')}` |",
        f"| Open alerts | `{_review_model_scalar(ghas_blocker_details.get('open_alerts') or 0)}` |",
        f"| Current alerts | `{_review_model_scalar(ghas_blocker_details.get('current_alerts') or 0)}` |",
        f"| Stale alerts | `{_review_model_scalar(ghas_blocker_details.get('stale_alerts') or 0)}` |",
        f"| Current head SHA | `{_markdown_table_value(ghas_blocker_details.get('current_head_sha') or 'unknown')}` |",
        f"| Dismissal allowed | `{_review_model_scalar(ghas_blocker_details.get('dismissal_allowed'))}` |",
    ]
    if (
        _int(ghas_blocker_details.get("open_alerts")) > 0
        and _int(ghas_blocker_details.get("current_alerts")) == 0
        and _int(ghas_blocker_details.get("stale_alerts")) > 0
    ):
        ghas_body.extend(
            [
                "",
                "> Stale-only Code Scanning state: no alert currently matches the PR head SHA. Wait for Code Scanning refresh; do not patch or dismiss stale alerts.",
                "",
            ]
        )

    if ghas_findings:
        ghas_body.extend(["", "### Code Scanning alert details", ""])
        for finding in ghas_findings[:5]:
            alert_number = _markdown_table_value(finding.get("number") or "unknown")
            alert_url = _string(finding.get("url"))
            alert_label = f"[#{alert_number}]({alert_url})" if alert_url else f"#{alert_number}"
            ghas_body.extend(
                [
                    f"#### {alert_label} — `{_markdown_table_value(finding.get('rule_id') or 'unknown')}`",
                    "",
                    "| Field | Value |",
                    "|---|---|",
                    f"| Severity | `{_markdown_table_value(finding.get('severity') or 'unknown')}` |",
                    f"| Location | `{_markdown_table_value(finding.get('location') or 'unknown')}` |",
                    f"| Freshness | `{_markdown_table_value(finding.get('freshness') or 'unknown')}` |",
                    f"| Alert SHA | `{_markdown_table_value(finding.get('alert_commit_sha') or 'unknown')}` |",
                    f"| PR head SHA | `{_markdown_table_value(finding.get('current_head_sha') or 'unknown')}` |",
                    f"| Recommended action | `{_markdown_table_value(finding.get('recommended_action') or 'review_alert_freshness')}` |",
                    f"| Dismissal allowed | `{_review_model_scalar(finding.get('dismissal_allowed'))}` |",
                    f"| Dismissal guidance | `{_markdown_table_value(finding.get('dismissal_guidance') or 'manual_review_required')}` |",
                ]
            )
            message = _string(finding.get("message"))
            if message:
                ghas_body.extend(["", f"> {message}", ""])
            commands = [
                str(command)
                for command in _as_list(finding.get("proof_commands"))
                if isinstance(command, str) and command.strip()
            ]
            if commands:
                ghas_body.extend(["", "Proof:", "", "```bash", *commands[:5], "```", ""])

    lines.extend(
        _details(
            (
                "🛡️ GHAS / CodeQL refresh details"
                if stale_only_security_signal
                else "🛡️ GHAS / CodeQL blocker details"
            ),
            ghas_body,
            open_by_default=ghas_open,
        )
    )
    lines.append("")

    proof_section_title = (
        "🧪 Optional verification" if review_state == "ready" else "🧪 Proof to rerun"
    )
    proof_body: list[str] = []
    if proof_commands:
        proof_body.extend(["```bash", *proof_commands, "```"])
    else:
        proof_body.append("`none`")
    lines.extend(
        _details(
            proof_section_title,
            proof_body,
            open_by_default=proof_open,
        )
    )
    lines.append("")

    check_body = [
        "| Check group | Count / names |",
        "|---|---|",
        f"| Failed checks | `{failed_total}` / `{_markdown_table_value(_joined(failed_check_names))}` |",
        f"| Queued required checks | `{queued_total}` / `{_markdown_table_value(_joined(queued_check_names))}` |",
        f"| Startup failures | `{startup_total}` / `{_markdown_table_value(_joined(startup_failure_names))}` |",
        f"| Missing required contexts | `{missing_total}` / `{_markdown_table_value(_joined(missing_context_names))}` |",
    ]
    lines.extend(
        _details(
            "✅ Passing / queued / missing check evidence",
            check_body,
            open_by_default=False,
        )
    )
    lines.append("")

    lines.extend(
        [
            "## Authority boundary",
            "",
            "| Authority | Value |",
            "|---|---|",
            f"| Boundary mode | `{_review_model_scalar(authority.get('boundary_mode'))}` |",
            f"| Patch automation | `{_review_model_scalar(authority.get('patch_automation'))}` |",
            f"| Security dismissal | `{_review_model_scalar(authority.get('security_dismissal'))}` |",
            f"| Merge authorization | `{_review_model_scalar(authority.get('merge_authorization'))}` |",
            f"| Semantic equivalence claim | `{_review_model_scalar(authority.get('semantic_equivalence_claim'))}` |",
            "",
            "> This summary is generated from the structured PR Quality review model. It is reporting-only and does not authorize merge, patch automation, security dismissal, or semantic-equivalence claims.",
        ]
    )

    return "\n".join(lines) + "\n"


def _html_escape(value: object) -> str:
    return (
        _review_model_scalar(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_pr_quality_artifacts_manifest(model: JsonObject) -> JsonObject:
    artifacts = [
        item
        for item in (_as_dict(candidate) for candidate in _as_list(model.get("artifact_index")))
        if _string(item.get("path"))
    ]
    if not artifacts:
        artifacts = _review_model_artifact_index()

    authority_evidence_sources = _authority_evidence_source_index()
    expected_paths: list[str] = []
    for item in [*artifacts, *authority_evidence_sources]:
        artifact_path = _string(item.get("path"))
        if artifact_path and artifact_path not in expected_paths:
            expected_paths.append(artifact_path)
    authority_evidence_source_paths = [
        _string(item.get("path"))
        for item in authority_evidence_sources
        if _string(item.get("path"))
    ]
    missing_authority_evidence_paths = [
        artifact_path
        for artifact_path in authority_evidence_source_paths
        if artifact_path not in expected_paths
    ]
    expected_artifact_inventory_verification = {
        "status": (
            "passed" if expected_paths and not missing_authority_evidence_paths else "failed"
        ),
        "non_empty": bool(expected_paths),
        "authority_aware": not missing_authority_evidence_paths,
        "expected_artifact_count": len(expected_paths),
        "authority_evidence_source_count": len(authority_evidence_source_paths),
        "missing_authority_evidence_paths": missing_authority_evidence_paths,
        "reporting_only": True,
        "authority_boundary": {
            "patch_automation": False,
            "security_dismissal": False,
            "merge_authorization": False,
            "semantic_equivalence_claim": False,
        },
    }

    primary_entrypoint = next(
        (
            _string(item.get("path"))
            for item in artifacts
            if bool(item.get("primary")) and _string(item.get("path"))
        ),
        expected_paths[0] if expected_paths else "index.html",
    )

    decision = _normalized_review_decision(model)
    authority = _as_dict(model.get("authority_boundary"))

    return {
        "schema_version": "sdetkit.pr_quality.artifacts_manifest.v1",
        "review_model_schema_version": _string(model.get("schema_version")),
        "review_model_schema": _as_dict(model.get("schema")),
        "generated_by": "sdetkit.pr_quality_action_report",
        "primary_entrypoint": primary_entrypoint,
        "expected_artifact_paths": expected_paths,
        "expected_artifact_inventory_verification": expected_artifact_inventory_verification,
        "artifacts": artifacts,
        "authority_evidence_sources": authority_evidence_sources,
        "reporting_only": True,
        "authority_boundary": {
            "boundary_mode": _string(authority.get("boundary_mode") or "reporting_only"),
            "patch_automation": bool(authority.get("patch_automation", False)),
            "security_dismissal": bool(authority.get("security_dismissal", False)),
            "merge_authorization": bool(authority.get("merge_authorization", False)),
            "semantic_equivalence_claim": bool(authority.get("semantic_equivalence_claim", False)),
        },
        "decision": {
            "status": _review_model_scalar(decision.get("status") or "unknown"),
            "review_state": _review_model_state(model),
            "merge_assessment": _review_model_scalar(decision.get("merge_assessment") or "unknown"),
            "next_action": _review_model_scalar(decision.get("next_action") or "unknown"),
        },
    }


def render_pr_quality_artifact_index_html(model: JsonObject) -> str:
    decision = _normalized_review_decision(model)
    authority = _as_dict(model.get("authority_boundary"))

    review_state = _review_model_state(model)
    status_label = _review_model_state_label(review_state)
    status_class = _review_model_state_class(review_state)
    merge_assessment = _review_model_scalar(decision.get("merge_assessment") or "unknown")
    next_action = _review_model_scalar(decision.get("next_action") or "unknown")
    risk_surface = _review_model_scalar(decision.get("risk_surface") or "unknown")

    artifact_index = [
        item
        for item in (_as_dict(candidate) for candidate in _as_list(model.get("artifact_index")))
        if _string(item.get("path"))
    ]
    if not artifact_index:
        artifact_index = _review_model_artifact_index()

    artifact_rows = [
        (
            _string(item.get("path")),
            "Open " + _string(item.get("title") or item.get("path")),
            _string(item.get("description") or item.get("surface") or "PR Quality artifact."),
        )
        for item in artifact_index
        if _string(item.get("path")) != "pr-quality-comment"
    ]

    authority_evidence_sources = [
        item
        for item in (
            _as_dict(candidate) for candidate in _as_list(model.get("authority_evidence_sources"))
        )
        if _string(item.get("path"))
    ]
    if not authority_evidence_sources:
        authority_evidence_sources = _authority_evidence_source_index()

    authority_source_rows = [
        (
            _string(item.get("path")),
            "Open " + _string(item.get("title") or item.get("path")),
            _string(
                item.get("description")
                or item.get("surface")
                or "PR Quality authority evidence source."
            ),
        )
        for item in authority_evidence_sources
    ]

    expected_artifact_paths: list[str] = []
    for item in [*artifact_index, *authority_evidence_sources]:
        artifact_path = _string(item.get("path"))
        if artifact_path and artifact_path not in expected_artifact_paths:
            expected_artifact_paths.append(artifact_path)

    expected_artifact_items = "\n".join(
        f"<li><code>{_html_escape(artifact_path)}</code></li>"
        for artifact_path in expected_artifact_paths
    )

    authority_evidence_source_paths = [
        _string(item.get("path"))
        for item in authority_evidence_sources
        if _string(item.get("path"))
    ]
    missing_authority_evidence_paths = [
        artifact_path
        for artifact_path in authority_evidence_source_paths
        if artifact_path not in expected_artifact_paths
    ]
    expected_inventory_status = (
        "passed" if expected_artifact_paths and not missing_authority_evidence_paths else "failed"
    )
    expected_inventory_rows = [
        ("Status", expected_inventory_status),
        ("Non-empty", bool(expected_artifact_paths)),
        ("Authority-aware", not missing_authority_evidence_paths),
        ("Expected artifact count", len(expected_artifact_paths)),
        ("Authority evidence source count", len(authority_evidence_source_paths)),
        (
            "Missing authority evidence paths",
            ", ".join(missing_authority_evidence_paths)
            if missing_authority_evidence_paths
            else "none",
        ),
        ("Reporting only", True),
        ("Patch automation", False),
        ("Security dismissal", False),
        ("Merge authorization", False),
        ("Semantic equivalence claim", False),
    ]

    expected_inventory_table = "\n".join(
        f"<tr><th>{_html_escape(label)}</th><td><code>{_html_escape(value)}</code></td></tr>"
        for label, value in expected_inventory_rows
    )

    def artifact_cards(rows: list[tuple[str, str, str]]) -> str:
        return "\n".join(
            '<article class="artifact-card">'
            f'<a href="{_html_escape(href)}">{_html_escape(title)}</a>'
            f"<span><code>{_html_escape(href)}</code></span>"
            f"<p>{_html_escape(description)}</p>"
            "</article>"
            for href, title, description in rows
        )

    authority_rows = [
        ("Boundary mode", authority.get("boundary_mode")),
        ("Patch automation", authority.get("patch_automation")),
        ("Security dismissal", authority.get("security_dismissal")),
        ("Merge authorization", authority.get("merge_authorization")),
        ("Semantic equivalence claim", authority.get("semantic_equivalence_claim")),
    ]

    authority_table = "\n".join(
        f"<tr><th>{_html_escape(label)}</th><td><code>{_html_escape(value)}</code></td></tr>"
        for label, value in authority_rows
    )

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "  <title>PR Quality Artifact Center</title>\n"
        "  <style>\n"
        "    :root { color-scheme: light dark; --bg: #0d1117; --panel: #161b22; --border: #30363d; --text: #e6edf3; --muted: #8b949e; --accent: #2f81f7; --green: #3fb950; --orange: #f0b72f; --red: #f85149; --code: #0b1220; }\n"
        "    * { box-sizing: border-box; }\n"
        "    body { margin: 0; background: radial-gradient(circle at top left, #132238, var(--bg) 42rem); color: var(--text); font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.45; }\n"
        "    main { max-width: 980px; margin: 0 auto; padding: 2rem; }\n"
        "    .hero, .card, .artifact-card { border: 1px solid var(--border); border-radius: 18px; background: rgba(22,27,34,0.92); padding: 1rem; box-shadow: 0 18px 42px rgba(0,0,0,0.22); }\n"
        "    .hero { padding: 1.5rem; background: linear-gradient(135deg, rgba(47,129,247,0.16), rgba(63,185,80,0.08)), var(--panel); }\n"
        "    .eyebrow { color: var(--muted); font-size: 0.82rem; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; }\n"
        "    h1 { margin: 0.35rem 0 0.75rem; font-size: clamp(1.8rem, 4vw, 3rem); }\n"
        "    h2 { margin: 0 0 1rem; }\n"
        "    .status-badge { display: inline-flex; border-radius: 999px; padding: 0.35rem 0.78rem; font-weight: 900; border: 1px solid var(--border); text-transform: uppercase; letter-spacing: 0.06em; }\n"
        "    .status-green { color: var(--green); background: rgba(63,185,80,0.12); }\n"
        "    .status-review { color: var(--orange); background: rgba(240,183,47,0.12); }\n"
        "    .status-failed { color: var(--red); background: rgba(248,81,73,0.14); }\n"
        "    .summary-grid, .artifact-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 0.8rem; margin-top: 1rem; }\n"
        "    .summary-card span, .artifact-card span { display: block; color: var(--muted); font-size: 0.82rem; margin-top: 0.25rem; }\n"
        "    .summary-card { border: 1px solid var(--border); border-radius: 14px; background: rgba(13,17,23,0.48); padding: 1rem; }\n"
        "    .artifact-card a { color: var(--text); font-size: 1.05rem; font-weight: 800; text-decoration: none; }\n"
        "    .artifact-card a:hover { color: var(--accent); text-decoration: underline; }\n"
        "    .artifact-card p { color: var(--muted); margin-bottom: 0; }\n    .path-list { margin: 0; padding-left: 1.2rem; color: var(--muted); }\n    .path-list li { margin: 0.35rem 0; }\n"
        "    table { width: 100%; border-collapse: collapse; }\n"
        "    th, td { border-bottom: 1px solid var(--border); padding: 0.65rem; text-align: left; vertical-align: top; }\n"
        "    th { width: 38%; color: var(--muted); }\n"
        "    code { background: var(--code); border: 1px solid var(--border); border-radius: 8px; padding: 0.12rem 0.32rem; }\n"
        "    .card { margin-top: 1rem; }\n"
        "    .boundary { color: var(--muted); border-left: 4px solid var(--accent); padding-left: 0.8rem; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        '    <section class="hero">\n'
        '      <div class="eyebrow">SDET Quality Gate</div>\n'
        "      <h1>PR Quality Artifact Center</h1>\n"
        f'      <span class="status-badge {status_class}">{_html_escape(status_label)}</span>\n'
        '      <div class="summary-grid">\n'
        f'        <article class="summary-card"><span>Merge assessment</span><strong>{_html_escape(merge_assessment)}</strong></article>\n'
        f'        <article class="summary-card"><span>Next action</span><strong>{_html_escape(next_action)}</strong></article>\n'
        f'        <article class="summary-card"><span>Risk surface</span><strong>{_html_escape(risk_surface)}</strong></article>\n'
        "      </div>\n"
        "    </section>\n"
        '    <section class="card">\n'
        "      <h2>Artifact entry points</h2>\n"
        '      <div class="artifact-grid">\n'
        f"        {artifact_cards(artifact_rows)}\n"
        "      </div>\n"
        "    </section>\n"
        '    <section class="card">\n'
        "      <h2>Expected artifact inventory verification</h2>\n"
        '      <p class="boundary">Reporting-only verification. This verification explains expected artifact completeness and does not authorize merge, patch automation, security dismissal, or semantic-equivalence claims.</p>\n'
        f"      <table>{expected_inventory_table}</table>\n"
        "    </section>\n"
        '    <section class="card">\n'
        "      <h2>Expected artifact inventory</h2>\n"
        '      <p class="boundary">Reporting-only expected-path inventory. This inventory describes review artifacts and does not authorize merge, patch automation, security dismissal, or semantic-equivalence claims.</p>\n'
        '      <ul class="path-list">\n'
        f"        {expected_artifact_items}\n"
        "      </ul>\n"
        "    </section>\n"
        '    <section class="card">\n'
        "      <h2>Authority evidence sources</h2>\n"
        '      <p class="boundary">Reporting-only source map. This source map explains authority evidence and does not authorize patch automation, security dismissal, merge, or semantic-equivalence claims.</p>\n'
        '      <div class="artifact-grid">\n'
        f"        {artifact_cards(authority_source_rows)}\n"
        "      </div>\n"
        "    </section>\n"
        '    <section class="card">\n'
        "      <h2>Authority boundary</h2>\n"
        f"      <table>{authority_table}</table>\n"
        '      <p class="boundary">Reporting-only. This artifact center does not authorize merge, patch automation, security dismissal, or semantic-equivalence claims.</p>\n'
        "    </section>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def render_pr_quality_review_html(model: JsonObject) -> str:
    decision = _normalized_review_decision(model)
    authority = _as_dict(model.get("authority_boundary"))
    primary_blocker = _as_dict(model.get("primary_blocker"))
    failure_vector_signal = _as_dict(model.get("failure_vector_signal"))
    proof_commands = [
        str(command)
        for command in _as_list(model.get("proof_to_rerun"))
        if isinstance(command, str) and command.strip()
    ]
    recommended_actions = [
        str(item)
        for item in _as_list(model.get("recommended_actions"))
        if isinstance(item, str) and item.strip()
    ]
    failed_check_names = [
        str(item)
        for item in _as_list(model.get("failed_check_names"))
        if isinstance(item, str) and item.strip()
    ]
    queued_check_names = [
        str(item)
        for item in _as_list(model.get("required_queued_check_names"))
        if isinstance(item, str) and item.strip()
    ]
    startup_failure_names = [
        str(item)
        for item in _as_list(model.get("required_startup_failure_names"))
        if isinstance(item, str) and item.strip()
    ]
    missing_context_names = [
        str(item)
        for item in _as_list(model.get("missing_required_context_names"))
        if isinstance(item, str) and item.strip()
    ]

    def _count(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    status = _review_model_scalar(
        decision.get("source_status") or decision.get("status") or "unknown"
    )
    review_state = _review_model_state(model)
    status_class = _review_model_state_class(review_state)
    hero_label = _review_model_state_label(review_state)
    state_caption = {
        "waiting": (
            "Required checks are still running. Wait for the named checks "
            "before changing or merging the pull request."
        ),
        "blocked": (
            "A required proof contract is blocked. Resolve the named blocker "
            "and rerun the focused proof."
        ),
        "review": (
            "Automated proof is complete, but the listed evidence requires "
            "human review before merge."
        ),
        "ready": (
            "Automated proof is complete and internally consistent. Review "
            "scope, risk, and authority before deciding."
        ),
        "stale": (
            "Published evidence does not represent the current pull request "
            "state. Refresh exact-head evidence before review or merge."
        ),
        "invalid": (
            "The review evidence contradicts itself. Repair the evidence "
            "model before relying on this verdict."
        ),
    }.get(review_state, "Review the current PR Quality evidence.")

    next_action = _review_model_scalar(decision.get("next_action") or "unknown")
    merge_assessment = _review_model_scalar(decision.get("merge_assessment") or "unknown")
    risk_surface = _review_model_scalar(decision.get("risk_surface") or "unknown")
    signal = _review_model_scalar(decision.get("comment_signal") or "none")
    first_blocker = _review_model_scalar(decision.get("primary_blocker") or "none")
    first_action = next_action

    failed_total = _count(decision.get("failed_checks"))
    queued_total = _count(decision.get("required_queued_checks"))
    startup_total = _count(decision.get("required_startup_failures"))
    missing_total = _count(decision.get("missing_required_contexts"))
    review_first = bool(decision.get("review_first_evidence"))
    needs_attention = review_state != "ready"

    hero_class = f"hero {status_class}"

    decision_rows = [
        ("Review state", review_state),
        ("Source status", status),
        ("Merge assessment", decision.get("merge_assessment")),
        ("Next action", decision.get("next_action")),
        ("Risk surface", decision.get("risk_surface")),
        ("Signal title", decision.get("signal_title")),
        ("Signal", decision.get("comment_signal")),
        ("First blocker", first_blocker),
        ("First blocker action", first_action),
        ("Review-first evidence", decision.get("review_first_evidence")),
        ("Failed checks", decision.get("failed_checks")),
        ("Required queued checks", decision.get("required_queued_checks")),
        ("Required startup failures", decision.get("required_startup_failures")),
        ("Missing required contexts", decision.get("missing_required_contexts")),
        ("Cleared security signal", decision.get("cleared_security_signal")),
    ]
    blocker_rows = [
        ("Title", first_blocker),
        ("Surface", primary_blocker.get("surface") or risk_surface),
        ("Action", first_action),
        ("Code", primary_blocker.get("code")),
        ("Path", primary_blocker.get("path")),
        ("Details", primary_blocker.get("details")),
    ]
    failure_vector_rows = [
        ("Source", failure_vector_signal.get("source") or "none"),
        ("Headline signal", failure_vector_signal.get("headline_signal") or "none"),
        ("Actual failure", failure_vector_signal.get("actual_failure") or "none"),
        ("Failure type", failure_vector_signal.get("failure_type") or "none"),
        ("Failing command", failure_vector_signal.get("failing_command") or "none"),
        ("Failing test/check", failure_vector_signal.get("failing_test_or_check") or "none"),
        ("Exit code", failure_vector_signal.get("exit_code")),
        ("Owner hint", failure_vector_signal.get("owner_hint") or "none"),
        ("Safe-fix candidate", failure_vector_signal.get("safe_fix_candidate")),
        ("Safe-fix allowed", failure_vector_signal.get("safe_fix_allowed")),
        ("Reporting only", failure_vector_signal.get("reporting_only")),
    ]
    authority_rows = [
        ("Boundary mode", authority.get("boundary_mode")),
        ("Patch automation", authority.get("patch_automation")),
        ("Security dismissal", authority.get("security_dismissal")),
        ("Merge authorization", authority.get("merge_authorization")),
        ("Semantic equivalence claim", authority.get("semantic_equivalence_claim")),
    ]
    metric_rows = [
        ("Failed checks", failed_total),
        ("Queued required checks", queued_total),
        ("Startup failures", startup_total),
        ("Missing contexts", missing_total),
        ("Review-first", review_first),
    ]
    artifact_rows = [
        (
            _string(item.get("path")),
            _string(item.get("description") or item.get("title") or "PR Quality artifact"),
        )
        for item in (_as_dict(candidate) for candidate in _as_list(model.get("artifact_index")))
        if _string(item.get("path"))
    ]
    if not artifact_rows:
        artifact_rows = [
            (
                _string(item.get("path")),
                _string(item.get("description") or item.get("title") or "PR Quality artifact"),
            )
            for item in _review_model_artifact_index()
        ]

    def table(rows: list[tuple[str, object]]) -> str:
        body = "\n".join(
            f"<tr><th>{_html_escape(label)}</th><td><code>{_html_escape(value)}</code></td></tr>"
            for label, value in rows
        )
        return f"<table>{body}</table>"

    def metric_cards(rows: list[tuple[str, object]]) -> str:
        return "\n".join(
            '<article class="metric-card">'
            f'<span class="metric-label">{_html_escape(label)}</span>'
            f"<strong>{_html_escape(value)}</strong>"
            "</article>"
            for label, value in rows
        )

    def artifact_cards(rows: list[tuple[str, object]]) -> str:
        return "\n".join(
            '<article class="artifact-card">'
            f"<strong><code>{_html_escape(name)}</code></strong>"
            f"<span>{_html_escape(description)}</span>"
            "</article>"
            for name, description in rows
        )

    def list_panel(title: str, items: list[str]) -> str:
        if not items:
            return (
                '<article class="signal-card">'
                f"<h3>{_html_escape(title)}</h3>"
                "<p><code>none</code></p>"
                "</article>"
            )
        body = "".join(f"<li>{_html_escape(item)}</li>" for item in items)
        return (
            f'<article class="signal-card"><h3>{_html_escape(title)}</h3><ul>{body}</ul></article>'
        )

    if proof_commands:
        proof_html = (
            "<pre><code>"
            + "\n".join(_html_escape(command) for command in proof_commands)
            + "</code></pre>"
        )
    else:
        proof_html = "<p><code>none</code></p>"

    first_recommended_action = first_action
    triage_html = ""
    if needs_attention:
        triage_html = (
            '<section class="alert-card">'
            f"<h2>{_html_escape(hero_label.title())}</h2>"
            '<div class="triage-grid">'
            f"<article><span>First blocker</span><strong>{_html_escape(first_blocker)}</strong></article>"
            f"<article><span>Recommended action</span><strong>{_html_escape(first_recommended_action)}</strong></article>"
            f"<article><span>Failed checks</span><strong>{_html_escape(failed_total)}</strong></article>"
            f"<article><span>Missing contexts</span><strong>{_html_escape(missing_total)}</strong></article>"
            f"<article><span>Actual failure</span><strong>{_html_escape(failure_vector_signal.get('actual_failure') or 'none')}</strong></article>"
            f"<article><span>Owner hint</span><strong>{_html_escape(failure_vector_signal.get('owner_hint') or 'none')}</strong></article>"
            "</div>"
            "</section>"
        )

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "  <title>PR Quality Review Dashboard</title>\n"
        "  <style>\n"
        "    :root { color-scheme: light dark; --bg: #0d1117; --panel: #161b22; --panel-2: #0f1720; --border: #30363d; --text: #e6edf3; --muted: #8b949e; --accent: #2f81f7; --green: #3fb950; --orange: #f0b72f; --red: #f85149; --code: #0b1220; }\n"
        "    * { box-sizing: border-box; }\n"
        "    body { margin: 0; background: radial-gradient(circle at top left, #132238, var(--bg) 42rem); color: var(--text); font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.45; }\n"
        "    main { max-width: 1120px; margin: 0 auto; padding: 2rem; }\n"
        "    .hero { position: relative; overflow: hidden; border: 1px solid var(--border); border-radius: 22px; padding: 1.6rem; background: linear-gradient(135deg, rgba(47,129,247,0.18), rgba(63,185,80,0.08)), var(--panel); box-shadow: 0 22px 56px rgba(0,0,0,0.34); }\n"
        "    .hero::before { content: ''; position: absolute; inset: 0; pointer-events: none; background: radial-gradient(circle at top right, rgba(255,255,255,0.08), transparent 18rem); }\n"
        "    .hero > * { position: relative; z-index: 1; }\n"
        "    .hero.status-failed { border-color: rgba(248,81,73,0.55); background: linear-gradient(135deg, rgba(248,81,73,0.16), rgba(240,183,47,0.08)), var(--panel); }\n"
        "    .hero.status-review { border-color: rgba(240,183,47,0.50); background: linear-gradient(135deg, rgba(240,183,47,0.16), rgba(47,129,247,0.08)), var(--panel); }\n"
        "    .hero.status-green { border-color: rgba(63,185,80,0.45); background: linear-gradient(135deg, rgba(63,185,80,0.14), rgba(47,129,247,0.08)), var(--panel); }\n"
        "    .eyebrow { color: var(--muted); font-size: 0.82rem; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; }\n"
        "    h1 { margin: 0.35rem 0 0.75rem; font-size: clamp(1.8rem, 4vw, 3rem); }\n"
        "    h2 { margin: 0 0 1rem; }\n"
        "    h3 { margin: 0 0 0.5rem; }\n"
        "    .hero-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }\n"
        "    .state-caption { max-width: 780px; margin: 0.2rem 0 0; color: var(--muted); font-size: 1rem; }\n"
        "    .hero-grid, .metrics, .artifact-grid, .signal-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 0.8rem; margin-top: 1rem; }\n"
        "    .hero-card, .metric-card, .artifact-card, .signal-card, .card, .alert-card { border: 1px solid var(--border); border-radius: 16px; background: rgba(22,27,34,0.90); padding: 1rem; box-shadow: 0 10px 28px rgba(0,0,0,0.18); }\n"
        "    .hero-card span, .metric-label, .artifact-card span, .alert-card span { display: block; color: var(--muted); font-size: 0.82rem; margin-bottom: 0.25rem; }\n"
        "    .status-badge { display: inline-flex; align-items: center; border-radius: 999px; padding: 0.38rem 0.78rem; font-weight: 900; border: 1px solid var(--border); text-transform: uppercase; letter-spacing: 0.06em; white-space: nowrap; }\n"
        "    .status-green { color: var(--green); background: rgba(63,185,80,0.12); }\n"
        "    .status-review { color: var(--orange); background: rgba(240,183,47,0.12); }\n"
        "    .status-failed { color: var(--red); background: rgba(248,81,73,0.14); }\n"
        "    .alert-card { border-color: rgba(248,81,73,0.55); background: linear-gradient(135deg, rgba(248,81,73,0.16), rgba(240,183,47,0.08)), var(--panel); margin-top: 1rem; }\n"
        "    .triage-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.8rem; }\n"
        "    .triage-grid article { border: 1px solid var(--border); border-radius: 12px; padding: 0.8rem; background: rgba(13,17,23,0.55); }\n"
        "    .layout { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr); gap: 1rem; margin-top: 1rem; }\n"
        "    @media (max-width: 860px) { .layout { grid-template-columns: 1fr; } main { padding: 1rem; } }\n"
        "    table { border-collapse: collapse; width: 100%; overflow: hidden; border-radius: 10px; }\n"
        "    th, td { border-bottom: 1px solid var(--border); padding: 0.68rem; text-align: left; vertical-align: top; }\n"
        "    th { width: 34%; color: var(--muted); font-weight: 700; }\n"
        "    code, pre { background: var(--code); border: 1px solid var(--border); border-radius: 8px; }\n"
        "    code { padding: 0.12rem 0.32rem; }\n"
        "    pre { padding: 1rem; overflow-x: auto; white-space: pre-wrap; overflow-wrap: anywhere; }\n"
        "    .boundary { color: var(--muted); border-left: 4px solid var(--accent); padding-left: 0.8rem; }\n"
        "    .card { margin-top: 1rem; }\n"
        "    .section-kicker { color: var(--muted); display: block; font-size: 0.76rem; font-weight: 800; letter-spacing: 0.10em; text-transform: uppercase; margin-bottom: 0.25rem; }\n"
        "    .artifact-card strong, .signal-card h3 { overflow-wrap: anywhere; }\n"
        "    .signal-card ul { margin: 0.4rem 0 0; padding-left: 1.2rem; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        f'    <section class="{hero_class}">\n'
        '      <div class="hero-top">\n'
        "        <div>\n"
        '          <div class="eyebrow">SDET Quality Gate</div>\n'
        "          <h1>PR Quality Review Dashboard</h1>\n"
        f'          <p class="state-caption">{_html_escape(state_caption)}</p>\n'
        "        </div>\n"
        f'        <span class="status-badge {status_class}">{_html_escape(hero_label)}</span>\n'
        "      </div>\n"
        '      <div class="hero-grid">\n'
        f'        <article class="hero-card"><span>Merge assessment</span><strong>{_html_escape(merge_assessment)}</strong></article>\n'
        f'        <article class="hero-card"><span>Next reviewer action</span><strong>{_html_escape(next_action)}</strong></article>\n'
        f'        <article class="hero-card"><span>Risk surface</span><strong>{_html_escape(risk_surface)}</strong></article>\n'
        f'        <article class="hero-card"><span>Signal</span><strong>{_html_escape(signal)}</strong></article>\n'
        "      </div>\n"
        "    </section>\n"
        f"    {triage_html}\n"
        '    <section class="metrics">\n'
        f"      {metric_cards(metric_rows)}\n"
        "    </section>\n"
        '    <section class="layout">\n'
        '      <article class="card">\n'
        '        <span class="section-kicker">Review model</span>\n'
        "        <h2>Decision details</h2>\n"
        f"        {table(decision_rows)}\n"
        "      </article>\n"
        '      <article class="card">\n'
        '        <span class="section-kicker">Triage</span>\n'
        "        <h2>First blocker</h2>\n"
        f"        {table(blocker_rows)}\n"
        "      </article>\n"
        '      <article class="card">\n'
        '        <span class="section-kicker">FailureVector</span>\n'
        "        <h2>Failure vector signal</h2>\n"
        f"        {table(failure_vector_rows)}\n"
        '        <p class="boundary">Reporting-only FailureVector projection. This signal does not authorize safe-fix execution, patch automation, or merge.</p>\n'
        "      </article>\n"
        "    </section>\n"
        '    <section class="card">\n'
        '      <span class="section-kicker">Live inputs</span>\n'
        "      <h2>Failure signals</h2>\n"
        '      <div class="signal-grid">\n'
        f"        {list_panel('Failed checks', failed_check_names)}\n"
        f"        {list_panel('Queued required checks', queued_check_names)}\n"
        f"        {list_panel('Startup failures', startup_failure_names)}\n"
        f"        {list_panel('Missing required contexts', missing_context_names)}\n"
        f"        {list_panel('Recommended actions', recommended_actions)}\n"
        "      </div>\n"
        "    </section>\n"
        '    <section class="layout">\n'
        '      <article class="card">\n'
        '        <span class="section-kicker">Operator proof</span>\n'
        "        <h2>Proof to rerun</h2>\n"
        f"        {proof_html}\n"
        "      </article>\n"
        '      <article class="card">\n'
        '        <span class="section-kicker">Safety boundary</span>\n'
        "        <h2>Authority boundary</h2>\n"
        f"        {table(authority_rows)}\n"
        '        <p class="boundary">Reporting-only. This dashboard does not authorize merge, patch automation, security dismissal, or semantic-equivalence claims.</p>\n'
        "      </article>\n"
        "    </section>\n"
        '    <section class="card">\n'
        '      <span class="section-kicker">Artifact bundle</span>\n'
        "      <h2>Product artifacts</h2>\n"
        '      <div class="artifact-grid">\n'
        f"        {artifact_cards(artifact_rows)}\n"
        "      </div>\n"
        "    </section>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def render_comment_body(
    *,
    action_report: JsonObject,
    check_intelligence: JsonObject,
    evidence_narrative: JsonObject | None = None,
    safe_fix_outcome: JsonObject | None = None,
    trajectory_records: list[JsonObject] | None = None,
    runtime_proof_artifacts: JsonObject | None = None,
    security_finding_diagnosis: JsonObject | None = None,
) -> str:
    evidence_narrative = evidence_narrative or {}
    safe_fix_outcome = safe_fix_outcome or _as_dict(check_intelligence.get("safe_fix_outcome"))
    trajectory_records = trajectory_records or []
    remediation_refresh = _as_dict(check_intelligence.get("remediation_refresh"))
    status = _string(action_report.get("status") or "unknown")
    status_needs_operator = status != "green"
    evidence_signal_heading, evidence_signal_lines, evidence_review_required = _evidence_signal(
        evidence_narrative
    )
    evidence_signal_heading, evidence_signal_lines, evidence_review_required = (
        _reconciled_evidence_signal(
            check_intelligence=check_intelligence,
            action_report=action_report,
            evidence_narrative=evidence_narrative,
            heading=evidence_signal_heading,
            lines=evidence_signal_lines,
            review_required=evidence_review_required,
            security_finding_diagnosis=security_finding_diagnosis,
        )
    )

    lines = [
        "## SDETKit Review Result: "
        + _result_title(
            status,
            evidence_signal_present=bool(evidence_signal_lines),
            evidence_review_required=evidence_review_required,
        ),
        "",
        f"Status: `{status}`",
        "",
    ]

    reviewer_dashboard = _reviewer_dashboard_lines(
        status=status,
        evidence_signal_heading=evidence_signal_heading,
        evidence_signal_lines=evidence_signal_lines,
        evidence_review_required=evidence_review_required,
        action_report=action_report,
        check_intelligence=check_intelligence,
        evidence_narrative=evidence_narrative,
    )
    lines.extend(["## Reviewer dashboard", "", *reviewer_dashboard, ""])

    quality = _quality_lines(evidence_narrative)
    if quality:
        lines.extend(["## Quality summary", "", *quality, ""])

    if evidence_signal_lines:
        lines.extend(["## " + evidence_signal_heading, "", *evidence_signal_lines, ""])

    security_diagnosis = _security_finding_diagnosis_lines(security_finding_diagnosis)
    if security_diagnosis:
        lines.extend(
            [
                *_operator_section(
                    "Security finding diagnosis",
                    security_diagnosis,
                    open_when=status_needs_operator or evidence_review_required,
                ),
                "",
            ]
        )

    patch_plan = _patch_plan_lines(evidence_narrative)
    if patch_plan:
        lines.extend(
            [
                *_operator_section(
                    "Review-first patch plan",
                    patch_plan,
                    open_when=status in {"review_required", "safe_fix_available"},
                ),
                "",
            ]
        )

    trajectory = _trajectory_lines(trajectory_records)
    if trajectory:
        lines.extend(
            [
                *_operator_section(
                    "Trajectory summary",
                    trajectory,
                    open_when=status_needs_operator,
                ),
                "",
            ]
        )

    runtime_proof = _runtime_proof_artifact_lines(runtime_proof_artifacts)
    if runtime_proof:
        lines.extend(
            [
                *_operator_section(
                    "Runtime proof artifacts",
                    runtime_proof,
                    open_when=status_needs_operator,
                ),
                "",
            ]
        )

    operator_summary = _operator_safetygate_summary_lines(
        action_report=action_report,
        trajectory_records=trajectory_records,
        runtime_proof_artifacts=runtime_proof_artifacts or {},
    )
    if operator_summary:
        lines.extend(
            [
                *_operator_section(
                    "Operator SafetyGate summary",
                    operator_summary,
                    open_when=status_needs_operator,
                ),
                "",
            ]
        )

    primary_blocker_lines = _primary_blocker_lines(_as_dict(action_report.get("primary_blocker")))
    automation_decision_lines = _automation_lines(action_report)
    safe_fix_lines = [
        *_safe_fix_outcome_lines(_as_dict(safe_fix_outcome)),
        "",
        "Remediation refresh",
        *_remediation_refresh_lines(_as_dict(remediation_refresh)),
    ]
    evidence_collected_lines = _evidence_lines(check_intelligence, action_report)
    failed_check_lines = _failed_check_lines(check_intelligence)
    recommended_action_lines = _bullet_lines(_as_list(action_report.get("recommended_actions")))
    required_proof_lines = _command_lines(_as_list(action_report.get("proof_commands")))

    has_primary_blocker = _as_dict(action_report.get("primary_blocker")) != {}
    has_failed_checks = bool(_as_list(check_intelligence.get("failed_checks")))
    has_recommended_actions = _has_operator_content(recommended_action_lines)
    has_required_proof = _has_operator_content(required_proof_lines)
    lines.extend(
        [
            *_operator_section(
                "Primary blocker",
                primary_blocker_lines,
                open_when=status_needs_operator or has_primary_blocker,
            ),
            "",
            *_operator_section(
                "Automation decision",
                automation_decision_lines,
                open_when=status_needs_operator,
            ),
            "",
            *_operator_section(
                "Safe fix outcome",
                safe_fix_lines,
                open_when=status in {"safe_fix_available", "review_required"},
            ),
            "",
            *_operator_section(
                "Evidence collected",
                evidence_collected_lines,
                open_when=status_needs_operator,
            ),
            "",
            *_operator_section(
                "Failed check diagnoses",
                failed_check_lines,
                open_when=has_failed_checks,
            ),
            "",
            *_operator_section(
                "Recommended actions",
                recommended_action_lines,
                open_when=status_needs_operator or has_recommended_actions,
            ),
            "",
            *_operator_section(
                "Required proof",
                required_proof_lines,
                open_when=status_needs_operator or has_required_proof,
            ),
            "",
        ]
    )

    if status == "green":
        if evidence_review_required:
            lines.extend(
                [
                    "## Merge assessment",
                    "",
                    "- Evidence review signal present; quality gate passed, but review-first evidence requires human review before merge.",
                    "",
                ]
            )
        elif evidence_signal_lines:
            lines.extend(
                [
                    "## Merge assessment",
                    "",
                    "- Evidence proof signal present; verify the listed proof before routine merge.",
                    "",
                ]
            )
        else:
            lines.extend(["## Merge assessment", "", "- No action required from SDETKit.", ""])

    rendered = "\n".join(lines)
    for phrase in BANNED_EDUCATIONAL_PHRASES:
        if phrase in rendered:
            raise ValueError(f"educational PR Quality phrase leaked into action report: {phrase}")
    return rendered


def write_comment_body(
    *,
    action_report_path: Path,
    check_intelligence_path: Path,
    out: Path,
    review_model_out: Path | None = None,
    review_summary_out: Path | None = None,
    review_html_out: Path | None = None,
    review_index_out: Path | None = None,
    review_artifacts_manifest_out: Path | None = None,
    evidence_narrative_path: Path | None = None,
    trajectory_jsonl_path: Path | None = None,
    runtime_proof_artifacts_path: Path | None = None,
    security_finding_diagnosis_path: Path | None = None,
    failure_bundle_out_dir: Path | None = None,
    pr_number: int = 0,
    head_sha: str = "",
    base_sha: str = "",
) -> JsonObject:
    action_report = _read_json(action_report_path)
    check_intelligence = _read_json(check_intelligence_path)
    evidence_narrative = _read_json(evidence_narrative_path)
    trajectory_records = _read_jsonl(trajectory_jsonl_path)
    runtime_proof_artifacts = _read_json(runtime_proof_artifacts_path)
    security_finding_diagnosis = _read_json(security_finding_diagnosis_path)

    body = render_comment_body(
        action_report=action_report,
        check_intelligence=check_intelligence,
        evidence_narrative=evidence_narrative,
        trajectory_records=trajectory_records,
        runtime_proof_artifacts=runtime_proof_artifacts,
        security_finding_diagnosis=security_finding_diagnosis,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")

    failure_bundle_result: JsonObject = {}
    if failure_bundle_out_dir is not None:
        bundle = build_current_head_failure_bundle(
            pr_number=pr_number,
            head_sha=head_sha
            or _string(check_intelligence.get("head_sha") or action_report.get("head_sha")),
            base_sha=base_sha
            or _string(check_intelligence.get("base_sha") or action_report.get("base_sha")),
            check_intelligence=check_intelligence,
            action_report=action_report,
            diagnostic_vectors=_as_dict(
                check_intelligence.get("diagnostic_vectors")
                or action_report.get("diagnostic_vectors")
            ),
            remediation_plans=_as_dict(
                check_intelligence.get("remediation_plans")
                or action_report.get("remediation_plans")
            ),
            safe_fix_outcome=_as_dict(
                check_intelligence.get("safe_fix_outcome") or action_report.get("safe_fix_outcome")
            ),
            refresh_summary=_as_dict(
                check_intelligence.get("remediation_refresh")
                or action_report.get("remediation_refresh")
            ),
            trajectory_records=trajectory_records,
            trajectory_jsonl_path=(
                trajectory_jsonl_path.as_posix() if trajectory_jsonl_path is not None else ""
            ),
        )
        written_bundle_paths = write_current_head_failure_bundle(
            bundle,
            failure_bundle_out_dir,
        )
        manifest = _as_dict(bundle.get("manifest"))
        failure_bundle_result = {
            "out_dir": failure_bundle_out_dir.as_posix(),
            "files": [item.as_posix() for item in written_bundle_paths],
            "report_path": (failure_bundle_out_dir / "failure-bundle.md").as_posix(),
            "safety_summary": {
                "review_first": bool(manifest.get("review_first", False)),
                "safe_fix_allowed": bool(manifest.get("safe_fix_allowed", False)),
                "reporting_only": True,
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        }

    status = _string(action_report.get("status") or "unknown")
    _heading, evidence_signal_lines, evidence_review_required = _evidence_signal(evidence_narrative)
    _heading, evidence_signal_lines, evidence_review_required = _reconciled_evidence_signal(
        check_intelligence=check_intelligence,
        action_report=action_report,
        evidence_narrative=evidence_narrative,
        heading=_heading,
        lines=evidence_signal_lines,
        review_required=evidence_review_required,
        security_finding_diagnosis=security_finding_diagnosis,
    )
    if evidence_review_required:
        evidence_signal_kind = "review"
    elif evidence_signal_lines:
        evidence_signal_kind = "proof"
    else:
        evidence_signal_kind = "none"

    review_model = build_pr_quality_review_model(
        status=status,
        evidence_signal_heading=_heading,
        evidence_signal_lines=evidence_signal_lines,
        evidence_review_required=evidence_review_required,
        action_report=action_report,
        check_intelligence=check_intelligence,
        evidence_narrative=evidence_narrative,
    )
    review_model_written = False
    if review_model_out is not None:
        review_model_out.parent.mkdir(parents=True, exist_ok=True)
        review_model_out.write_text(
            json.dumps(review_model, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        review_model_written = True

    review_summary_written = False
    if review_summary_out is not None:
        review_summary_out.parent.mkdir(parents=True, exist_ok=True)
        review_summary_out.write_text(
            render_pr_quality_review_summary(review_model),
            encoding="utf-8",
        )
        review_summary_written = True

    review_html_written = False
    if review_html_out is not None:
        review_html_out.parent.mkdir(parents=True, exist_ok=True)
        review_html_out.write_text(
            render_pr_quality_review_html(review_model),
            encoding="utf-8",
        )
        review_html_written = True

    review_index_written = False
    if review_index_out is not None:
        review_index_out.parent.mkdir(parents=True, exist_ok=True)
        review_index_out.write_text(
            render_pr_quality_artifact_index_html(review_model),
            encoding="utf-8",
        )
        review_index_written = True

    review_artifacts_manifest = build_pr_quality_artifacts_manifest(review_model)
    review_artifacts_manifest_written = False
    if review_artifacts_manifest_out is not None:
        review_artifacts_manifest_out.parent.mkdir(parents=True, exist_ok=True)
        review_artifacts_manifest_out.write_text(
            json.dumps(
                review_artifacts_manifest,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        review_artifacts_manifest_written = True

    trajectory_summary = _trajectory_summary(trajectory_records)
    repo_memory_runtime = (
        _as_dict(runtime_proof_artifacts.get("repo_memory")) if runtime_proof_artifacts else {}
    )
    expected_inventory_verification = _as_dict(
        review_artifacts_manifest.get("expected_artifact_inventory_verification")
    )
    expected_inventory_authority = _as_dict(
        expected_inventory_verification.get("authority_boundary")
    )

    def expected_inventory_key(*parts: str) -> str:
        return "_".join(("expected", "artifact", "inventory", *parts))

    result: JsonObject = {
        "out": out.as_posix(),
        "review_model_out": review_model_out.as_posix() if review_model_out is not None else "",
        "review_model_written": review_model_written,
        "review_model_schema_version": _string(review_model.get("schema_version")),
        "review_summary_out": review_summary_out.as_posix()
        if review_summary_out is not None
        else "",
        "review_summary_written": review_summary_written,
        "review_html_out": review_html_out.as_posix() if review_html_out is not None else "",
        "review_html_written": review_html_written,
        "review_index_out": review_index_out.as_posix() if review_index_out is not None else "",
        "review_index_written": review_index_written,
        "review_artifacts_manifest_out": review_artifacts_manifest_out.as_posix()
        if review_artifacts_manifest_out is not None
        else "",
        "review_artifacts_manifest_written": review_artifacts_manifest_written,
        expected_inventory_key("status"): _string(
            expected_inventory_verification.get("status") or "not_collected"
        ),
        expected_inventory_key("non", "empty"): bool(
            expected_inventory_verification.get("non_empty", False)
        ),
        expected_inventory_key("authority", "aware"): bool(
            expected_inventory_verification.get("authority_aware", False)
        ),
        expected_inventory_key("expected", "artifact", "count"): _int(
            expected_inventory_verification.get("expected_artifact_count")
        ),
        expected_inventory_key("authority", "evidence", "source", "count"): _int(
            expected_inventory_verification.get("authority_evidence_source_count")
        ),
        expected_inventory_key("missing", "authority", "evidence", "path", "count"): len(
            _as_list(expected_inventory_verification.get("missing_authority_evidence_paths"))
        ),
        expected_inventory_key("reporting", "only"): bool(
            expected_inventory_verification.get("reporting_only", False)
        ),
        expected_inventory_key("patch", "automation"): bool(
            expected_inventory_authority.get("patch_automation", False)
        ),
        expected_inventory_key("security", "dismissal"): bool(
            expected_inventory_authority.get("security_dismissal", False)
        ),
        expected_inventory_key("merge", "authorization"): bool(
            expected_inventory_authority.get("merge_authorization", False)
        ),
        expected_inventory_key("semantic", "equivalence", "claim"): bool(
            expected_inventory_authority.get("semantic_equivalence_claim", False)
        ),
        "status": status,
        "result_title": _result_title(
            status,
            evidence_signal_present=bool(evidence_signal_lines),
            evidence_review_required=evidence_review_required,
        ),
        "evidence_signal_kind": evidence_signal_kind,
        "evidence_signal_present": bool(evidence_signal_lines),
        "evidence_review_required": evidence_review_required,
        "trajectory_signal_present": trajectory_summary["record_count"] > 0,
        "trajectory_record_count": trajectory_summary["record_count"],
        "trajectory_review_first_count": trajectory_summary["review_first_count"],
        "trajectory_auto_fix_allowed_count": trajectory_summary["auto_fix_allowed_count"],
        "runtime_proof_artifacts_present": bool(runtime_proof_artifacts),
        "runtime_proof_collection_status": _string(
            runtime_proof_artifacts.get("status") if runtime_proof_artifacts else "not_collected"
        ),
        "runtime_guard_violation_count": _int(
            _as_dict(runtime_proof_artifacts.get("isolated_proof")).get(
                "runtime_guard_violation_count"
            )
            if runtime_proof_artifacts
            else 0
        ),
        "live_benchmark_collection_status": _string(
            _as_dict(runtime_proof_artifacts.get("live_benchmark")).get("collection_status")
            if runtime_proof_artifacts
            else "not_collected"
        ),
        "live_benchmark_status": _string(
            _as_dict(runtime_proof_artifacts.get("live_benchmark")).get("status")
            if runtime_proof_artifacts
            else "not_collected"
        ),
        "live_benchmark_scenario_count": _int(
            _as_dict(runtime_proof_artifacts.get("live_benchmark")).get("scenario_count")
            if runtime_proof_artifacts
            else 0
        ),
        "anti_cheat_rejection_count": _int(
            _as_dict(runtime_proof_artifacts.get("live_benchmark")).get(
                "anti_cheat_rejection_count"
            )
            if runtime_proof_artifacts
            else 0
        ),
        "repo_memory_collection_status": _string(
            _as_dict(runtime_proof_artifacts.get("repo_memory")).get("collection_status")
            if runtime_proof_artifacts
            else "not_collected"
        ),
        "repo_memory_status": _string(
            _as_dict(runtime_proof_artifacts.get("repo_memory")).get("status")
            if runtime_proof_artifacts
            else "not_collected"
        ),
        "repo_memory_live_contract_proven": bool(
            repo_memory_runtime.get("live_contract_proven", False)
        ),
        _repo_memory_trajectory_authority_key("status"): _string(
            repo_memory_runtime.get(_trajectory_authority_key("status")) or "not_collected"
        ),
        _repo_memory_trajectory_authority_key("record", "count"): _int(
            repo_memory_runtime.get(_trajectory_authority_key("record", "count"))
        ),
        _repo_memory_trajectory_authority_key("review", "first", "count"): _int(
            repo_memory_runtime.get(_trajectory_authority_key("review", "first", "count"))
        ),
        _repo_memory_trajectory_authority_key("auto", "fix", "allowed", "count"): _int(
            repo_memory_runtime.get(_trajectory_authority_key("auto", "fix", "allowed", "count"))
        ),
        _repo_memory_trajectory_authority_key("reporting", "only", "count"): _int(
            repo_memory_runtime.get(_trajectory_authority_key("reporting", "only", "count"))
        ),
        _repo_memory_trajectory_authority_key("patch", "application", "allowed"): bool(
            repo_memory_runtime.get(
                _trajectory_authority_key("patch", "application", "allowed"), False
            )
        ),
        _repo_memory_trajectory_authority_key("security", "dismissal", "allowed"): bool(
            repo_memory_runtime.get(
                _trajectory_authority_key("security", "dismissal", "allowed"), False
            )
        ),
        _repo_memory_trajectory_authority_key("merge", "authorized"): bool(
            repo_memory_runtime.get(_trajectory_authority_key("merge", "authorized"), False)
        ),
        _repo_memory_trajectory_authority_key("semantic", "equivalence", "proven"): bool(
            repo_memory_runtime.get(
                _trajectory_authority_key("semantic", "equivalence", "proven"), False
            )
        ),
        TRUSTED_HISTORY_COLLECTION_STATUS: _string(
            _as_dict(runtime_proof_artifacts.get(TRUSTED_HISTORY)).get("collection_status")
            if runtime_proof_artifacts
            else "not_collected"
        ),
        TRUSTED_HISTORY_STATUS: _string(
            _as_dict(runtime_proof_artifacts.get(TRUSTED_HISTORY)).get("status")
            if runtime_proof_artifacts
            else "not_collected"
        ),
        TRUSTED_HISTORY_RECORD_COUNT: _int(
            _as_dict(runtime_proof_artifacts.get(TRUSTED_HISTORY)).get("record_count")
            if runtime_proof_artifacts
            else 0
        ),
        TRUSTED_HISTORY_BASE_ANCESTRY_VERIFIED: bool(
            _as_dict(runtime_proof_artifacts.get(TRUSTED_HISTORY)).get(
                BASE_ANCESTRY_VERIFIED, False
            )
            if runtime_proof_artifacts
            else False
        ),
        TRUSTED_HISTORY_PRIOR_INPUT_READ_ONLY: bool(
            _as_dict(runtime_proof_artifacts.get(TRUSTED_HISTORY)).get(
                PRIOR_HISTORY_READ_ONLY_INPUT, False
            )
            if runtime_proof_artifacts
            else False
        ),
        TRUSTED_HISTORY_AUTOMATION_ALLOWED: bool(
            _as_dict(runtime_proof_artifacts.get(TRUSTED_HISTORY)).get("automation_allowed", False)
            if runtime_proof_artifacts
            else False
        ),
        TRUSTED_HISTORY_MERGE_AUTHORIZED: bool(
            _as_dict(runtime_proof_artifacts.get(TRUSTED_HISTORY)).get("merge_authorized", False)
            if runtime_proof_artifacts
            else False
        ),
        TRUSTED_HISTORY_SEMANTIC_EQUIVALENCE_PROVEN: bool(
            _as_dict(runtime_proof_artifacts.get(TRUSTED_HISTORY)).get(
                "semantic_equivalence_proven", False
            )
            if runtime_proof_artifacts
            else False
        ),
    }
    if failure_bundle_result:
        result["failure_bundle"] = failure_bundle_result
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.pr_quality_action_report")
    parser.add_argument("--action-report", type=Path, required=True)
    parser.add_argument("--check-intelligence", type=Path, required=True)
    parser.add_argument("--evidence-narrative", type=Path)
    parser.add_argument("--trajectory-jsonl", type=Path)
    parser.add_argument("--runtime-proof-artifacts", type=Path)
    parser.add_argument("--security-finding-diagnosis", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--review-model-out", type=Path)
    parser.add_argument("--review-summary-out", type=Path)
    parser.add_argument("--review-html-out", type=Path)
    parser.add_argument("--review-index-out", type=Path)
    parser.add_argument("--review-artifacts-manifest-out", type=Path)
    parser.add_argument("--failure-bundle-out-dir", type=Path)
    parser.add_argument("--pr-number", type=int, default=0)
    parser.add_argument("--head-sha", default="")
    parser.add_argument("--base-sha", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = write_comment_body(
        action_report_path=args.action_report,
        check_intelligence_path=args.check_intelligence,
        evidence_narrative_path=args.evidence_narrative,
        trajectory_jsonl_path=args.trajectory_jsonl,
        runtime_proof_artifacts_path=args.runtime_proof_artifacts,
        security_finding_diagnosis_path=args.security_finding_diagnosis,
        out=args.out,
        review_model_out=args.review_model_out,
        review_summary_out=args.review_summary_out,
        review_html_out=args.review_html_out,
        review_index_out=args.review_index_out,
        review_artifacts_manifest_out=args.review_artifacts_manifest_out,
        failure_bundle_out_dir=args.failure_bundle_out_dir,
        pr_number=args.pr_number,
        head_sha=args.head_sha,
        base_sha=args.base_sha,
    )
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


_BASE_AUTHORITY_EVIDENCE_SOURCE_INDEX = _authority_evidence_source_index


def _authority_evidence_source_index() -> list[JsonObject]:  # type: ignore[no-redef]  # noqa: F811
    sources = list(_BASE_AUTHORITY_EVIDENCE_SOURCE_INDEX())
    workflow_source = {
        "path": "workflow-governance/workflow-governance-report.json",
        "kind": "json",
        "surface": "authority_evidence",
        "title": "Workflow permission review evidence packet",
        "description": "Reporting-only workflow governance packet with required human evidence, blocked actions, permission groups, granted write scopes, and inferred permission reasons.",
        "format": "json",
        "reporting_only": True,
        "patch_automation": False,
        "security_dismissal": False,
        "merge_authorization": False,
        "semantic_equivalence_claim": False,
        "authority_boundary": {
            "patch_automation": False,
            "security_dismissal": False,
            "merge_authorization": False,
            "semantic_equivalence_claim": False,
        },
    }
    if not any(_string(item.get("path")) == workflow_source["path"] for item in sources):
        sources.append(workflow_source)
    return sources


_BASE_RENDER_PR_QUALITY_REVIEW_SUMMARY = render_pr_quality_review_summary


def render_pr_quality_review_summary(model: JsonObject) -> str:  # type: ignore[no-redef]  # noqa: F811
    body = _BASE_RENDER_PR_QUALITY_REVIEW_SUMMARY(model)
    packet = _as_dict(model.get("workflow_permission_review_evidence_packet"))
    section = _workflow_permission_review_packet_markdown_lines(packet)
    if not section or "## Workflow permission review evidence" in body:
        return body

    rendered_section = "\n".join(section)
    if "\n## Product artifacts" in body:
        return body.replace(
            "\n## Product artifacts", f"\n{rendered_section}\n\n## Product artifacts", 1
        )
    return body.rstrip() + "\n\n" + rendered_section + "\n"


_BASE_RENDER_PR_QUALITY_REVIEW_HTML = render_pr_quality_review_html


def render_pr_quality_review_html(model: JsonObject) -> str:  # type: ignore[no-redef]  # noqa: F811
    html = _BASE_RENDER_PR_QUALITY_REVIEW_HTML(model)
    panel = _workflow_permission_review_packet_html(
        _as_dict(model.get("workflow_permission_review_evidence_packet"))
    )
    if not panel or "Workflow permission review evidence" in html:
        return html
    if "</main>" in html:
        return html.replace("</main>", f"{panel}\n</main>", 1)
    return html


_BASE_RENDER_COMMENT_BODY = render_comment_body


def render_comment_body(*args: object, **kwargs: object) -> str:  # type: ignore[no-redef]  # noqa: F811
    body = _BASE_RENDER_COMMENT_BODY(*args, **kwargs)
    action_report = _as_dict(kwargs.get("action_report") or (args[0] if args else {}))
    check_intelligence = _as_dict(
        kwargs.get("check_intelligence") or (args[1] if len(args) > 1 else {})
    )
    packet = _workflow_permission_review_packet_from_sources(action_report, check_intelligence)
    section = _workflow_permission_review_packet_markdown_lines(packet)
    if not section or "## Workflow permission review evidence" in body:
        return body

    rendered_section = "\n".join(section)
    if "\n## Quality summary" in body:
        return body.replace(
            "\n## Quality summary", f"\n{rendered_section}\n\n## Quality summary", 1
        )
    return body.rstrip() + "\n\n" + rendered_section + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
