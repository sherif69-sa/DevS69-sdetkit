"""Build sanitized review-first diagnoses for PR security findings.

This module is deliberately advisory. It reads code-scanning alert metadata,
optionally examines the current checked-out source line in memory, and emits
diagnosis proposals without exposing source text or authorizing remediation or
dismissal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.security-finding-diagnosis.v1"
DEFAULT_OUT_DIR = Path("build") / "pr-quality" / "security-diagnosis"
JSON_NAME = "security-finding-diagnosis.json"
MARKDOWN_NAME = "security-finding-diagnosis.md"
TRUSTED_DISPOSITION_RECORD_SCHEMA = ".".join(
    ("sdetkit", "security", "reviewed", "disposition", "history", "record", "v2")
)
TRUSTED_REVIEWED_DISPOSITION_HISTORY = "_".join(("trusted", "reviewed", "disposition", "history"))
TRUSTED_REVIEWED_DISPOSITION_CONTEXT = "_".join(("trusted", "reviewed", "disposition", "context"))
MATCHING_REVIEWED_DISPOSITION_COUNT = "_".join(("matching", "reviewed", "disposition", "count"))
HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION = "_".join(
    ("historical", "disposition", "authorizes", "current", "action")
)
PR_SCOPE_VERIFICATION = "_".join(("pr", "scope", "verification"))
CHANGED_PATHS_PROVEN = "_".join(("changed", "paths", "proven"))
PATH_IN_MERGED_PR_CHANGED_FILES = "_".join(("path", "in", "merged", "pr", "changed", "files"))

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").strip()


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_jsonl(path: Path | None) -> list[JsonObject]:
    if path is None or not path.exists():
        return []

    records: list[JsonObject] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object on line {line_number} in {path}")
        records.append(payload)
    return records


def _thread_nodes(payload: Any) -> list[JsonObject]:
    raw = _as_dict(payload)
    pull_request = _as_dict(
        _as_dict(_as_dict(raw.get("data")).get("repository")).get("pullRequest")
    )
    threads = _as_dict(pull_request.get("reviewThreads"))
    return [_as_dict(item) for item in _as_list(threads.get("nodes")) if isinstance(item, dict)]


def _current_review_locations(payload: Any) -> set[tuple[str, int]]:
    locations: set[tuple[str, int]] = set()
    for thread in _thread_nodes(payload):
        if bool(thread.get("isResolved", False)) or bool(thread.get("isOutdated", False)):
            continue
        path = _string(thread.get("path"))
        line = _int_value(thread.get("line"))
        if path and line:
            locations.add((path, line))
    return locations


def _alert_records(payload: Any) -> tuple[str, list[JsonObject]]:
    if isinstance(payload, list):
        return "collected", [_as_dict(item) for item in payload if isinstance(item, dict)]

    data = _as_dict(payload)
    status = _string(data.get("collection_status") or "collected")
    alerts = [_as_dict(item) for item in _as_list(data.get("alerts")) if isinstance(item, dict)]
    return status, alerts


def _source_line(root: Path, relative_path: str, line: int) -> str:
    if not relative_path or line <= 0:
        return ""

    resolved_root = root.resolve()
    candidate = (resolved_root / relative_path).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        return ""
    if not candidate.is_file():
        return ""

    try:
        lines = candidate.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""

    if line > len(lines):
        return ""
    return lines[line - 1]


def _tool_name(alert: JsonObject) -> str:
    tool = _as_dict(alert.get("tool"))
    return _string(tool.get("name") or alert.get("tool_name") or "unknown")


def _rule_id(alert: JsonObject) -> str:
    rule = _as_dict(alert.get("rule"))
    return _string(rule.get("id") or alert.get("rule_id") or "unknown")


def _severity(alert: JsonObject) -> str:
    rule = _as_dict(alert.get("rule"))
    return _string(rule.get("security_severity_level") or rule.get("severity") or "unknown")


def _location(alert: JsonObject) -> tuple[str, int, str]:
    instance = _as_dict(alert.get("most_recent_instance"))
    location = _as_dict(instance.get("location"))
    return (
        _string(location.get("path")),
        _int_value(location.get("start_line")),
        _string(instance.get("commit_sha")),
    )


def _trusted_reviewed_disposition_index(
    history_path: Path | None,
) -> tuple[JsonObject, dict[tuple[str, str, str], list[JsonObject]]]:
    if history_path is None or not history_path.exists():
        return {
            "status": "not_collected",
            "record_count": 0,
            "reviewed_disposition_count": 0,
            "advisory_only": True,
            HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION: False,
        }, {}

    records = _read_jsonl(history_path)
    index: dict[tuple[str, str, str], list[JsonObject]] = {}
    count = 0
    for record in records:
        if _string(record.get("schema_version")) != TRUSTED_DISPOSITION_RECORD_SCHEMA:
            raise ValueError("trusted reviewed disposition history is not verified v2")
        source = _as_dict(record.get("source"))
        if source.get(PR_SCOPE_VERIFICATION) != CHANGED_PATHS_PROVEN:
            raise ValueError("trusted reviewed disposition record lacks changed-path provenance")
        boundary = _as_dict(record.get("decision_boundary"))
        if bool(boundary.get(HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION, False)):
            raise ValueError(
                "trusted reviewed disposition history expands current action authority"
            )
        if bool(boundary.get("automatic_security_fix_allowed", False)) or bool(
            boundary.get("automatic_dismissal_allowed", False)
        ):
            raise ValueError(
                "trusted reviewed disposition history expands security automation authority"
            )
        for raw_item in _as_list(record.get("reviewed_dispositions")):
            item = _as_dict(raw_item)
            if item.get(PATH_IN_MERGED_PR_CHANGED_FILES) is not True:
                raise ValueError("trusted reviewed disposition lacks merged-PR changed-file proof")
            key = (
                _string(item.get("tool")),
                _string(item.get("rule_id")),
                _string(item.get("path")),
            )
            if not all(key):
                raise ValueError("trusted reviewed disposition lacks exact-match identity")
            index.setdefault(key, []).append(item)
            count += 1

    return {
        "status": "verified_v2_read_only",
        "record_count": len(records),
        "reviewed_disposition_count": count,
        "advisory_only": True,
        HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION: False,
    }, index


def _trusted_reviewed_disposition_context(
    *,
    tool: str,
    rule_id: str,
    path: str,
    freshness: str,
    disposition_index: dict[tuple[str, str, str], list[JsonObject]],
) -> JsonObject:
    matches = disposition_index.get((tool, rule_id, path), []) if freshness == "current" else []
    latest = (
        sorted(matches, key=lambda item: _string(item.get("dismissed_at")), reverse=True)[0]
        if matches
        else {}
    )
    return {
        "status": "verified_prior_review_match" if matches else "no_verified_prior_review_match",
        MATCHING_REVIEWED_DISPOSITION_COUNT: len(matches),
        "latest_reviewed_pull_number": _int_value(latest.get("pull_number")),
        "latest_reviewed_reason": _string(latest.get("dismissed_reason")),
        "advisory_only": True,
        HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION: False,
    }


def _finding_id(tool: str, rule_id: str, path: str, line: int, number: Any) -> str:
    raw = "|".join([tool, rule_id, path, str(line), _string(number)])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"security-diagnosis-{digest}"


def _freshness(commit_sha: str, current_head_sha: str) -> str:
    if not commit_sha or not current_head_sha:
        return "unknown"
    return "current" if commit_sha == current_head_sha else "stale"


def _context_labels(*, path: str, source_line: str) -> list[str]:
    lowered = source_line.lower()
    labels: list[str] = []

    if path.startswith("tests/"):
        labels.append("test_only_path")
    if any(
        key in lowered
        for key in (
            "identity_handling",
            "schema_version",
            "classification",
            "source_workflow",
            "rule_id",
        )
    ):
        labels.append("public_metadata_key_context")
    if "assert " in lowered:
        labels.append("assertion_context")
    if any(token in lowered for token in ("test_", "fixture", "payload", "token=")):
        labels.append("test_or_fixture_context")
    if re.search(r"\b(api[_-]?key|token|secret|password|private[_-]?key)\b", lowered):
        labels.append("credential_name_context")
    if "should_not_leak" in lowered or "topsecret" in lowered:
        labels.append("approved_non_leaking_sentinel_context")
    if "print(" in lowered:
        labels.append("direct_print_call_context")

    return sorted(set(labels))


def _classification_payload(
    *,
    classification: str,
    recommended_action: str,
    diagnosis: str,
    evidence_labels: list[str],
    fix_proposal: str = "",
) -> JsonObject:
    return {
        "classification": classification,
        "recommended_action": recommended_action,
        "diagnosis": diagnosis,
        "evidence_labels": sorted(set(evidence_labels)),
        "fix_proposal": fix_proposal,
    }


def _classify(
    *,
    tool: str,
    rule_id: str,
    path: str,
    source_line: str,
    freshness: str,
) -> JsonObject:
    labels = _context_labels(path=path, source_line=source_line)

    if freshness == "stale":
        return _classification_payload(
            classification="stale_or_outdated_alert",
            recommended_action="wait_for_code_scanning_refresh",
            diagnosis="The alert does not point at the current PR head.",
            evidence_labels=["alert_commit_differs_from_current_head"],
        )

    if freshness != "current":
        return _classification_payload(
            classification="unknown_security_review_required",
            recommended_action="review_alert_freshness",
            diagnosis="The finding cannot be diagnosed until current-head provenance is confirmed.",
            evidence_labels=["current_head_provenance_unavailable"],
        )

    if tool.lower() == "codeql":
        return _classification_payload(
            classification="codeql_security_review_required",
            recommended_action="review_codeql_finding",
            diagnosis="A current CodeQL finding requires rule-specific human security review.",
            evidence_labels=[*labels, "codeql_tool"],
        )

    if tool != "sdetkit-security-gate":
        return _classification_payload(
            classification="unknown_security_review_required",
            recommended_action="review_current_finding",
            diagnosis="No proven rule-specific safe disposition applies to this scanner.",
            evidence_labels=[*labels, "unrecognized_security_tool"],
        )

    if rule_id == "SEC_DEBUG_PRINT" and "direct_print_call_context" in labels:
        return _classification_payload(
            classification="safe_mechanical_fix_candidate",
            recommended_action="propose_stdout_emission_repair",
            diagnosis=(
                "The scanner identified a direct print call in a source module; "
                "a narrow CLI-output hygiene repair can be proposed."
            ),
            evidence_labels=[*labels, "rule_specific_mechanical_repair"],
            fix_proposal="Replace direct print output with explicit stdout emission and rerun scanner proof.",
        )

    if rule_id == "SEC_SECRET_PATTERN":
        if "test_only_path" in labels and "test_or_fixture_context" in labels:
            return _classification_payload(
                classification="intentional_test_fixture_candidate",
                recommended_action="propose_test_sentinel_repair",
                diagnosis=(
                    "The current finding is in test-fixture context and may represent "
                    "non-production sentinel input; it still requires human confirmation."
                ),
                evidence_labels=[*labels, "secret_pattern_test_context"],
                fix_proposal=(
                    "After confirming test intent, replace scanner-like fixture data "
                    "with an approved non-leaking sentinel."
                ),
            )
        return _classification_payload(
            classification="true_positive_fix_required",
            recommended_action="investigate_and_fix_possible_secret",
            diagnosis=(
                "A current secret-pattern finding outside proven test-fixture context "
                "must be treated as a potential credential exposure."
            ),
            evidence_labels=[*labels, "secret_pattern_current_source"],
        )

    if rule_id == "SEC_HIGH_ENTROPY_STRING":
        if "public_metadata_key_context" in labels:
            return _classification_payload(
                classification="scanner_metadata_false_positive_candidate",
                recommended_action="propose_narrow_literal_repair",
                diagnosis=(
                    "The flagged current literal appears in descriptive metadata context, "
                    "not a proven credential sink; human review remains required."
                ),
                evidence_labels=[*labels, "high_entropy_metadata_context"],
                fix_proposal=(
                    "Replace the scanner-like descriptive label with a shorter equivalent "
                    "public label, then rerun scanner proof."
                ),
            )
        if "test_only_path" in labels:
            return _classification_payload(
                classification="scanner_test_literal_candidate",
                recommended_action="review_test_literal_or_use_approved_sentinel",
                diagnosis=(
                    "The high-entropy finding is located in test code, but is not yet "
                    "proven to be an intentional safe fixture."
                ),
                evidence_labels=[*labels, "high_entropy_test_context"],
            )
        return _classification_payload(
            classification="suspicious_literal_review_required",
            recommended_action="review_current_finding",
            diagnosis=(
                "A current high-entropy source literal requires review because no "
                "proven metadata or fixture context applies."
            ),
            evidence_labels=[*labels, "_".join(("high", "entropy", "unclassified", "source"))],
        )

    return _classification_payload(
        classification="unknown_security_review_required",
        recommended_action="review_current_finding",
        diagnosis="No proven rule-specific safe disposition applies to this finding.",
        evidence_labels=[*labels, "no_proven_safe_disposition"],
    )


def diagnose_alert(
    alert: JsonObject,
    *,
    current_head_sha: str,
    root: Path,
    review_locations: set[tuple[str, int]],
    reviewed_disposition_index: dict[tuple[str, str, str], list[JsonObject]] | None = None,
) -> JsonObject:
    tool = _tool_name(alert)
    rule_id = _rule_id(alert)
    path, line, commit_sha = _location(alert)
    freshness = _freshness(commit_sha, current_head_sha)
    source_line = _source_line(root, path, line) if freshness == "current" else ""
    diagnosis = _classify(
        tool=tool,
        rule_id=rule_id,
        path=path,
        source_line=source_line,
        freshness=freshness,
    )
    disposition_context = _trusted_reviewed_disposition_context(
        tool=tool,
        rule_id=rule_id,
        path=path,
        freshness=freshness,
        disposition_index=reviewed_disposition_index or {},
    )

    return {
        "finding_id": _finding_id(tool, rule_id, path, line, alert.get("number")),
        "alert_number": alert.get("number", ""),
        "tool": tool,
        "rule_id": rule_id,
        "severity": _severity(alert),
        "path": path,
        "line": line,
        "freshness": freshness,
        "review_thread_present": (path, line) in review_locations,
        **diagnosis,
        TRUSTED_REVIEWED_DISPOSITION_CONTEXT: disposition_context,
        "source_context_examined": bool(source_line),
        "sensitive_source_text_emitted": False,
        "human_review_required": True,
        "safe_to_auto_fix": False,
        "auto_dismiss_allowed": False,
        "automation_allowed": False,
    }


def build_security_finding_diagnosis(
    *,
    code_scanning_alerts: Path | None,
    review_threads: Path | None,
    current_head_sha: str,
    root: Path,
    trusted_reviewed_disposition_history_jsonl: Path | None = None,
) -> JsonObject:
    collection_status, alerts = _alert_records(_read_json(code_scanning_alerts))
    review_locations = _current_review_locations(_read_json(review_threads))
    trusted_history, reviewed_disposition_index = _trusted_reviewed_disposition_index(
        trusted_reviewed_disposition_history_jsonl
    )

    diagnoses: list[JsonObject] = []
    for alert in alerts:
        if _string(alert.get("state") or "open").lower() != "open":
            continue
        diagnoses.append(
            diagnose_alert(
                alert,
                current_head_sha=current_head_sha,
                root=root,
                review_locations=review_locations,
                reviewed_disposition_index=reviewed_disposition_index,
            )
        )

    diagnoses.sort(
        key=lambda item: (
            _string(item.get("path")),
            _int_value(item.get("line")),
            _string(item.get("rule_id")),
        )
    )
    counts = Counter(_string(item.get("classification")) for item in diagnoses)
    matched_current_findings = sum(
        1
        for item in diagnoses
        if _int_value(
            _as_dict(item.get(TRUSTED_REVIEWED_DISPOSITION_CONTEXT)).get(
                MATCHING_REVIEWED_DISPOSITION_COUNT
            )
        )
        > 0
    )
    trusted_history["matched_current_findings"] = matched_current_findings

    return {
        "schema_version": SCHEMA_VERSION,
        "collection_status": collection_status,
        "current_head_sha": current_head_sha,
        TRUSTED_REVIEWED_DISPOSITION_HISTORY: trusted_history,
        "diagnoses": diagnoses,
        "summary": {
            "open_findings": len(diagnoses),
            "current_findings": sum(1 for item in diagnoses if item.get("freshness") == "current"),
            "stale_findings": sum(1 for item in diagnoses if item.get("freshness") == "stale"),
            "scanner_metadata_false_positive_candidates": counts[
                "scanner_metadata_false_positive_candidate"
            ],
            "intentional_test_fixture_candidates": counts["intentional_test_fixture_candidate"],
            "safe_mechanical_fix_candidates": counts["safe_mechanical_fix_candidate"],
            "true_positive_fix_required": counts["true_positive_fix_required"],
            "unknown_security_review_required": counts["unknown_security_review_required"],
        },
        "decision_boundary": {
            "diagnosis_only": True,
            "human_review_required": True,
            "source_text_emitted": False,
            "automatic_security_fix_allowed": False,
            "automatic_dismissal_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION: False,
        },
    }


def render_markdown(report: JsonObject) -> str:
    summary = _as_dict(report.get("summary"))
    boundary = _as_dict(report.get("decision_boundary"))
    trusted_history = _as_dict(report.get(TRUSTED_REVIEWED_DISPOSITION_HISTORY))
    lines = [
        "# Security Finding Diagnosis",
        "",
        f"- Collection status: `{_string(report.get('collection_status'))}`",
        f"- Open findings: `{summary.get('open_findings', 0)}`",
        f"- Current findings: `{summary.get('current_findings', 0)}`",
        f"- Stale findings: `{summary.get('stale_findings', 0)}`",
        (
            "- Trusted reviewed disposition context: "
            f"`{_string(trusted_history.get('status') or 'not_collected')}`"
        ),
        (
            "- Current findings with verified prior review context: "
            f"`{_int_value(trusted_history.get('matched_current_findings'))}`"
        ),
        (
            "- Scanner metadata false-positive candidates: "
            f"`{summary.get('scanner_metadata_false_positive_candidates', 0)}`"
        ),
        (
            "- Intentional test-fixture candidates: "
            f"`{summary.get('intentional_test_fixture_candidates', 0)}`"
        ),
        "",
        "## Decision boundary",
        "",
        f"- Diagnosis only: `{str(bool(boundary.get('diagnosis_only'))).lower()}`",
        (
            "- Automatic security fix allowed: "
            f"`{str(bool(boundary.get('automatic_security_fix_allowed'))).lower()}`"
        ),
        (
            "- Automatic dismissal allowed: "
            f"`{str(bool(boundary.get('automatic_dismissal_allowed'))).lower()}`"
        ),
        (
            "- Historical disposition authorizes current action: "
            f"`{str(bool(boundary.get(HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION))).lower()}`"
        ),
        (f"- Safe mechanical fix candidates: `{summary.get('safe_mechanical_fix_candidates', 0)}`"),
        f"- True-positive fixes required: `{summary.get('true_positive_fix_required', 0)}`",
        "",
    ]

    for item in _as_list(report.get("diagnoses")):
        finding = _as_dict(item)
        disposition_context = _as_dict(finding.get(TRUSTED_REVIEWED_DISPOSITION_CONTEXT))
        lines.extend(
            [
                f"## `{_string(finding.get('rule_id'))}` — {_string(finding.get('path'))}",
                "",
                f"- Tool: `{_string(finding.get('tool'))}`",
                f"- Freshness: `{_string(finding.get('freshness'))}`",
                f"- Classification: `{_string(finding.get('classification'))}`",
                f"- Recommended action: `{_string(finding.get('recommended_action'))}`",
                f"- Human review required: `{str(bool(finding.get('human_review_required'))).lower()}`",
                (
                    "- Verified prior reviewed dispositions: "
                    f"`{_int_value(disposition_context.get(MATCHING_REVIEWED_DISPOSITION_COUNT))}`"
                ),
                (
                    "- Historical disposition authorizes current action: "
                    f"`{str(bool(disposition_context.get(HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION))).lower()}`"
                ),
                f"- Diagnosis: {_string(finding.get('diagnosis'))}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.security_finding_diagnosis")
    parser.add_argument("--code-scanning-alerts-json", type=Path)
    parser.add_argument("--review-threads-json", type=Path)
    parser.add_argument("--current-head-sha", required=True)
    parser.add_argument("--trusted-reviewed-disposition-history-jsonl", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_security_finding_diagnosis(
        code_scanning_alerts=args.code_scanning_alerts_json,
        review_threads=args.review_threads_json,
        current_head_sha=args.current_head_sha,
        root=args.root,
        trusted_reviewed_disposition_history_jsonl=args.trusted_reviewed_disposition_history_jsonl,
    )
    _write_json(args.out_dir / JSON_NAME, report)
    (args.out_dir / MARKDOWN_NAME).write_text(render_markdown(report), encoding="utf-8")

    summary = _as_dict(report.get("summary"))
    output = {
        "schema_version": SCHEMA_VERSION,
        "collection_status": report.get("collection_status", "unknown"),
        "open_findings": summary.get("open_findings", 0),
        "diagnosis_only": True,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
        "trusted_reviewed_disposition_history_status": _as_dict(
            report.get(TRUSTED_REVIEWED_DISPOSITION_HISTORY)
        ).get("status", "not_collected"),
        HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION: False,
    }
    rendered = (
        json.dumps(output, indent=2, sort_keys=True)
        if args.format == "json"
        else "\n".join(f"{key}={value}" for key, value in output.items())
    )
    sys.stdout.write(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
