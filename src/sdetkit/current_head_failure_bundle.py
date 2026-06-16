from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


SCHEMA_VERSION = "sdetkit.current_head_failure_bundle.v1"
TRAJECTORY_LINK_SCHEMA_VERSION = "sdetkit.current_head_trajectory_link.v1"
FAILED_STEP_EVIDENCE_KEY = "_".join(("failed", "step", "evidence"))
JOB_STEP_CONFIRMATION_KEY = "_".join(("job", "step", "confirmation"))
ARTIFACT_EVIDENCE_KEY = "_".join(("artifact", "evidence"))


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return bool(value)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _stable_json(payload: JsonObject) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _trajectory_link_summary(
    trajectory_records: list[JsonObject] | None,
    *,
    head_sha: str,
    trajectory_jsonl_path: str,
) -> JsonObject:
    normalized_head = _string(head_sha)
    linked: list[JsonObject] = []
    expanded_authority_fields: set[str] = set()

    denied = (
        "automation_allowed",
        "patch_application_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
        "automatic_security_fix_allowed",
        "automatic_dismissal_allowed",
    )

    for raw in _as_list(trajectory_records):
        record = _as_dict(raw)
        if not record:
            continue
        if not normalized_head:
            continue
        if _string(record.get("commit_sha")) != normalized_head:
            continue

        boundary = _as_dict(record.get("authority_boundary"))
        expanded = [key for key in denied if _bool(boundary.get(key))]
        expanded_authority_fields.update(expanded)

        decision = _as_dict(record.get("decision"))
        linked.append(
            {
                "trajectory_id": _string(record.get("trajectory_id")),
                "diagnostic_id": _string(record.get("diagnostic_id")),
                "generated_at": _string(record.get("generated_at")),
                "action": _string(record.get("action")),
                "final_result": _string(record.get("final_result")),
                "review_first": _bool(decision.get("review_first")),
                "auto_fix_allowed": _bool(decision.get("auto_fix_allowed")),
                "source_reporting_only": _bool(boundary.get("reporting_only")),
                "source_authority_expanded_fields": expanded,
            }
        )

    linked.sort(
        key=lambda item: (
            _string(item.get("generated_at")),
            _string(item.get("trajectory_id")),
        )
    )

    if expanded_authority_fields:
        status = "linked_review_required"
    elif linked:
        status = "linked"
    else:
        status = "not_found"

    return {
        "schema_version": TRAJECTORY_LINK_SCHEMA_VERSION,
        "status": status,
        "head_sha": normalized_head,
        "source_path": _string(trajectory_jsonl_path),
        "record_count": len(linked),
        "review_first_count": sum(_bool(item.get("review_first")) for item in linked),
        "auto_fix_allowed_count": sum(_bool(item.get("auto_fix_allowed")) for item in linked),
        "reporting_only_count": sum(_bool(item.get("source_reporting_only")) for item in linked),
        "expanded_authority_fields": sorted(expanded_authority_fields),
        "trajectory_ids": [
            _string(item.get("trajectory_id"))
            for item in linked
            if _string(item.get("trajectory_id"))
        ],
        "records": linked,
        "reporting_only": True,
        "current_pr_decision_input": False,
        "decision_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "proof_commands_executed": False,
        },
    }


def build_current_head_failure_bundle(
    *,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    check_intelligence: JsonObject | None = None,
    action_report: JsonObject | None = None,
    diagnostic_vectors: JsonObject | None = None,
    remediation_plans: JsonObject | None = None,
    safe_fix_outcome: JsonObject | None = None,
    refresh_summary: JsonObject | None = None,
    trajectory_records: list[JsonObject] | None = None,
    trajectory_jsonl_path: str = "",
    created_at: str = "",
) -> JsonObject:
    check_payload = _as_dict(check_intelligence)
    action_payload = _as_dict(action_report)
    vectors_payload = _as_dict(diagnostic_vectors)
    plans_payload = _as_dict(remediation_plans)
    safe_fix_payload = _as_dict(safe_fix_outcome)
    refresh_payload = _as_dict(refresh_summary)
    trajectory_history = _trajectory_link_summary(
        trajectory_records,
        head_sha=head_sha,
        trajectory_jsonl_path=trajectory_jsonl_path,
    )

    failed_checks = [_as_dict(item) for item in _as_list(check_payload.get("failed_checks"))]
    queued_checks = [_as_dict(item) for item in _as_list(check_payload.get("queued_checks"))]
    startup_failures = [_as_dict(item) for item in _as_list(check_payload.get("startup_failures"))]
    missing_required = _as_list(check_payload.get("missing_required_contexts"))

    review_first = _bool(action_payload.get("review_first")) or any(
        _bool(item.get("review_first")) for item in failed_checks
    )
    safe_fix_allowed = _bool(action_payload.get("safe_fix_available")) or any(
        _bool(item.get("safe_to_auto_fix")) for item in failed_checks
    )

    first_failures: list[JsonObject] = []
    for item in failed_checks:
        first_failure = _as_dict(item.get("first_failure"))
        if first_failure:
            first_failures.append(
                {
                    "check_name": _string(item.get("name")),
                    "line": _string(first_failure.get("line")),
                    "line_number": _int(first_failure.get("line_number")),
                    "tool": _string(first_failure.get("tool") or "unknown"),
                    "kind": _string(first_failure.get("kind") or "unknown"),
                    FAILED_STEP_EVIDENCE_KEY: _as_dict(item.get(FAILED_STEP_EVIDENCE_KEY)),
                    JOB_STEP_CONFIRMATION_KEY: _as_dict(item.get(JOB_STEP_CONFIRMATION_KEY)),
                    ARTIFACT_EVIDENCE_KEY: _as_dict(item.get(ARTIFACT_EVIDENCE_KEY)),
                }
            )

    owner_files: list[str] = []
    for item in failed_checks:
        diagnosis = _as_dict(item.get("diagnosis"))
        for path in _as_list(diagnosis.get("owner_files")):
            value = _string(path)
            if value and value not in owner_files:
                owner_files.append(value)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "pr_number": pr_number,
        "head_sha": _string(head_sha),
        "base_sha": _string(base_sha),
        "created_at": _string(created_at),
        "source": "pr_quality",
        "current_head": True,
        "checks_seen": _int(check_payload.get("checks_seen")),
        "failed_checks": len(failed_checks),
        "queued_checks": len(queued_checks),
        "required_queued_checks": len(
            [item for item in queued_checks if _bool(item.get("required"))]
        ),
        "startup_failures": len(startup_failures),
        "missing_required_contexts": len(missing_required),
        "review_first": review_first,
        "safe_fix_allowed": safe_fix_allowed,
        "trajectory_linked": _int(trajectory_history.get("record_count")) > 0,
        "trajectory_record_count": _int(trajectory_history.get("record_count")),
        "trajectory_review_first_count": _int(trajectory_history.get("review_first_count")),
        "trajectory_auto_fix_allowed_count": _int(trajectory_history.get("auto_fix_allowed_count")),
        "trajectory_source_path": _string(trajectory_history.get("source_path")),
        "bundle_files": [
            "manifest.json",
            "failure-bundle.json",
            "failure-bundle.md",
        ],
    }

    return {
        "manifest": manifest,
        "check_intelligence": check_payload,
        "action_report": action_payload,
        "first_failures": first_failures,
        "diagnostic_vectors": vectors_payload,
        "remediation_plans": plans_payload,
        "safe_fix_outcome": safe_fix_payload,
        "refresh_summary": refresh_payload,
        "trajectory_history": trajectory_history,
        "owner_files": owner_files,
    }


def render_current_head_failure_bundle_markdown(bundle: JsonObject) -> str:
    manifest = _as_dict(bundle.get("manifest"))
    first_failures = [_as_dict(item) for item in _as_list(bundle.get("first_failures"))]
    owner_files = [_string(item) for item in _as_list(bundle.get("owner_files")) if _string(item)]
    trajectory_history = _as_dict(bundle.get("trajectory_history"))
    trajectory_records = [
        _as_dict(item) for item in _as_list(trajectory_history.get("records")) if _as_dict(item)
    ]

    lines = [
        "# Current-head failure evidence bundle",
        "",
        f"- Schema: `{_string(manifest.get('schema_version'))}`",
        f"- PR: `#{_int(manifest.get('pr_number'))}`",
        f"- Head SHA: `{_string(manifest.get('head_sha') or 'unknown')}`",
        f"- Base SHA: `{_string(manifest.get('base_sha') or 'unknown')}`",
        f"- Checks seen: `{_int(manifest.get('checks_seen'))}`",
        f"- Failed checks: `{_int(manifest.get('failed_checks'))}`",
        f"- Required queued checks: `{_int(manifest.get('required_queued_checks'))}`",
        f"- Review first: `{str(_bool(manifest.get('review_first'))).lower()}`",
        f"- Safe fix allowed: `{str(_bool(manifest.get('safe_fix_allowed'))).lower()}`",
        "",
        "## First failures",
    ]

    if first_failures:
        for item in first_failures:
            location = (
                f"line {_int(item.get('line_number'))}"
                if _int(item.get("line_number"))
                else "line unknown"
            )
            lines.append(
                f"- `{_string(item.get('check_name') or 'unknown')}`: "
                f"`{_string(item.get('line'))}` ({location}, "
                f"{_string(item.get('tool') or 'unknown')}/{_string(item.get('kind') or 'unknown')})"
            )
            step = _as_dict(item.get(FAILED_STEP_EVIDENCE_KEY))
            if step:
                lines.append(
                    f"  - Failed step evidence: `{_string(step.get('status') or 'unknown')}`"
                )
                command = _string(step.get("command"))
                if command:
                    lines.append(f"  - Failed command: `{command}`")
                lines.append("- Reporting only: `true`")
                lines.append("- Automation allowed: `false`")
            artifact_evidence = _as_dict(item.get(ARTIFACT_EVIDENCE_KEY))
            if artifact_evidence:
                lines.append(
                    f"  - Artifact evidence: `{_string(artifact_evidence.get('status') or 'unknown')}`"
                )
                expected = [
                    _string(value)
                    for value in _as_list(artifact_evidence.get("expected_artifacts"))
                    if _string(value)
                ]
                if expected:
                    lines.append(
                        "  - Expected artifacts: "
                        + ", ".join(f"`{value}`" for value in expected[:5])
                    )
                lines.append("- Artifact automation allowed: `false`")
            confirmation = _as_dict(item.get(JOB_STEP_CONFIRMATION_KEY))
            if confirmation:
                lines.append(
                    f"  - Job step confirmation: `{_string(confirmation.get('status') or 'unknown')}`"
                )
                step_name = _string(confirmation.get("job_step_name"))
                if step_name:
                    lines.append(f"  - GitHub job step: `{step_name}`")
                lines.append("- Job step automation allowed: `false`")
    else:
        lines.append("- none")

    lines.extend(["", "## Owner files"])
    if owner_files:
        lines.extend(f"- `{path}`" for path in owner_files)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Current-head trajectory history",
            f"- Status: `{_string(trajectory_history.get('status') or 'not_found')}`",
            f"- Source: `{_string(trajectory_history.get('source_path') or 'none')}`",
            f"- Matching records: `{_int(trajectory_history.get('record_count'))}`",
            f"- Review-first records: `{_int(trajectory_history.get('review_first_count'))}`",
            (
                "- Auto-fix candidates observed: "
                f"`{_int(trajectory_history.get('auto_fix_allowed_count'))}`"
            ),
            "- Reporting only: `true`",
            "- Current PR decision input: `false`",
            "- Patch application allowed: `false`",
            "- Automation allowed: `false`",
            "- Merge authorized: `false`",
        ]
    )
    if trajectory_records:
        lines.extend(["", "### Linked trajectory records"])
        for item in trajectory_records:
            lines.append(
                f"- `{_string(item.get('trajectory_id') or 'unknown')}`: "
                f"`{_string(item.get('action') or 'none')}` / "
                f"`{_string(item.get('final_result') or 'unknown')}`"
            )
    else:
        lines.extend(["", "- none"])

    lines.append("")
    return "\n".join(lines)


def write_current_head_failure_bundle(bundle: JsonObject, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = _as_dict(bundle.get("manifest"))
    paths = [
        out_dir / "manifest.json",
        out_dir / "failure-bundle.json",
        out_dir / "failure-bundle.md",
    ]

    paths[0].write_text(_stable_json(manifest), encoding="utf-8")
    paths[1].write_text(_stable_json(bundle), encoding="utf-8")
    paths[2].write_text(render_current_head_failure_bundle_markdown(bundle), encoding="utf-8")

    return paths
