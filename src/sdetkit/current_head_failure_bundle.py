from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


SCHEMA_VERSION = "sdetkit.current_head_failure_bundle.v1"
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
    created_at: str = "",
) -> JsonObject:
    check_payload = _as_dict(check_intelligence)
    action_payload = _as_dict(action_report)
    vectors_payload = _as_dict(diagnostic_vectors)
    plans_payload = _as_dict(remediation_plans)
    safe_fix_payload = _as_dict(safe_fix_outcome)
    refresh_payload = _as_dict(refresh_summary)

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
        "owner_files": owner_files,
    }


def render_current_head_failure_bundle_markdown(bundle: JsonObject) -> str:
    manifest = _as_dict(bundle.get("manifest"))
    first_failures = [_as_dict(item) for item in _as_list(bundle.get("first_failures"))]
    owner_files = [_string(item) for item in _as_list(bundle.get("owner_files")) if _string(item)]

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
