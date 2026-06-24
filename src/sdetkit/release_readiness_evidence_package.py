"""Release-readiness evidence packaging.

This module builds a deterministic, reporting-only release evidence packet.
It inspects local release/package surfaces and summarizes what a human reviewer
should verify before a release. It never authorizes publishing, merging, patch
automation, security dismissal, or semantic-equivalence claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .report_provenance import (
    attach_provenance,
    build_input_provenance,
    check_report_path,
    render_freshness_text,
)

JsonObject = dict[str, Any]

SCHEMA_VERSION = "sdetkit.release_readiness_evidence_package.v2"
DEFAULT_OUT = "build/sdetkit/release-readiness-evidence/package.json"
DEFAULT_MARKDOWN_OUT = "build/sdetkit/release-readiness-evidence/package.md"
GENERATOR_SOURCE = "src/sdetkit/release_readiness_evidence_package.py"

_INPUT_PATHS: tuple[str, ...] = (
    "Makefile",
    ".github/workflows/release.yml",
    "docs/release-readiness-evidence-handoff.md",
    "docs/artifact-reference.md",
)

_AUTHORITY_BOUNDARY: JsonObject = {
    "boundary_mode": "reporting_only",
    "reporting_only": True,
    "repo_mutation": False,
    "issue_mutation_allowed": False,
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "release_authorization": False,
    "publish_authorization": False,
    "merge_authorization": False,
    "patch_automation": False,
    "security_dismissal": False,
    "semantic_equivalence_claim": False,
    "semantic_equivalence_proven": False,
}

_REQUIRED_EVIDENCE = [
    "package build command",
    "twine metadata check",
    "wheel contents check",
    "wheel smoke install",
    "release preflight",
    "release workflow provenance",
    "release diagnostics upload",
    "rollback or post-publish verification plan",
]

_PROOF_COMMANDS = [
    "make package-validate",
    "make release-preflight",
    "make release-verify-plan",
    (
        "python -m pytest -q tests/test_release_preflight.py "
        "tests/test_release_readiness.py tests/test_release_room_plan.py "
        "-o addopts="
    ),
    "make proof-after-format",
]


_PR_QUALITY_HANDOFF_SCHEMA = "sdetkit.pr_quality_publisher_handoff.v1"
_PR_QUALITY_SUMMARY_MANIFEST_PATH = "payload/pr-review-summary.md"
_PR_QUALITY_MANIFEST_PAYLOAD_PATHS = {
    "payload/pr-comment-body.md",
    "payload/pr-comment-metadata.json",
    _PR_QUALITY_SUMMARY_MANIFEST_PATH,
}
_PR_QUALITY_AUTHORITY_BOUNDARY: JsonObject = {
    "reporting_only": True,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}
_PR_QUALITY_DECISION_LABELS = {
    "Review state": "review_state",
    "First blocker": "first_blocker",
    "Next action": "next_action",
    "Required checks": "required_checks",
    "Security posture": "security_posture",
    "Merge posture": "merge_posture",
}
_PR_QUALITY_STATES = {
    "waiting",
    "blocked",
    "review",
    "ready",
    "stale",
    "invalid",
}
_PR_QUALITY_BLOCKING_STATES = {
    "waiting",
    "blocked",
    "review",
    "stale",
    "invalid",
}


def _resolve_input_path(
    root: Path,
    value: str | Path,
) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _optional_input_bytes(
    root: Path,
    value: str | Path | None,
) -> bytes:
    if value is None:
        return b"not_provided\0"
    return _read_input_bytes(_resolve_input_path(root, value))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_pr_quality_summary(summary: str) -> JsonObject:
    if not summary.lstrip().startswith("# PR Quality Review Summary"):
        raise ValueError("summary heading does not match the PR Quality contract")

    start_heading = "## Contributor decision"
    end_heading = "## Adaptive review details"
    start = summary.find(start_heading)
    end = summary.find(end_heading, start + len(start_heading))
    if start < 0 or end < 0 or end <= start:
        raise ValueError("summary contributor-decision section is missing")

    rows: dict[str, str] = {}
    section = summary[start:end]
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if stripped in {"| Item | Value |", "|---|---|"}:
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 2:
            raise ValueError("summary decision row must have two cells")

        label, value = cells
        if label not in _PR_QUALITY_DECISION_LABELS:
            raise ValueError(f"summary decision row is unknown: {label}")
        if label in rows:
            raise ValueError(f"summary decision row is duplicated: {label}")

        if value.startswith("`") and value.endswith("`"):
            value = value[1:-1]
        rows[label] = value

    if set(rows) != set(_PR_QUALITY_DECISION_LABELS):
        missing = sorted(set(_PR_QUALITY_DECISION_LABELS) - set(rows))
        raise ValueError(f"summary decision rows are incomplete: missing={missing}")

    projected = {key: rows[label] for label, key in _PR_QUALITY_DECISION_LABELS.items()}
    review_state = projected["review_state"]
    if review_state not in _PR_QUALITY_STATES:
        raise ValueError(f"summary review state is unsupported: {review_state}")
    return projected


def _pr_quality_handoff_result(
    *,
    collection_status: str,
    reason: str,
    summary_path: str = "",
    manifest_path: str = "",
    head_sha: str = "",
    head_matches: bool = False,
    decision: Mapping[str, Any] | None = None,
    release_review_blocking: bool = False,
    source_digests: Mapping[str, str] | None = None,
) -> JsonObject:
    decision_payload = dict(decision or {})
    return {
        "collection_status": collection_status,
        "available": collection_status == "collected",
        "reason": reason,
        "summary_path": summary_path,
        "manifest_path": manifest_path,
        "head_sha": head_sha,
        "head_matches": head_matches,
        "review_state": str(decision_payload.get("review_state", "unknown")),
        "first_blocker": str(decision_payload.get("first_blocker", "unknown")),
        "next_action": str(decision_payload.get("next_action", "unknown")),
        "required_checks": str(decision_payload.get("required_checks", "unknown")),
        "security_posture": str(decision_payload.get("security_posture", "unknown")),
        "merge_posture": str(decision_payload.get("merge_posture", "unknown")),
        "release_review_blocking": release_review_blocking,
        "reporting_only": True,
        "safe_to_publish": False,
        "release_authorized": False,
        "publish_authorized": False,
        "merge_authorized": False,
        "source_digests": dict(source_digests or {}),
        "authority_boundary": dict(_PR_QUALITY_AUTHORITY_BOUNDARY),
    }


def collect_pr_quality_handoff(
    *,
    repo_root: str | Path,
    expected_head_sha: str,
    summary_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> JsonObject:
    root = Path(repo_root).resolve()
    requested = summary_path is not None or manifest_path is not None
    if not requested:
        return _pr_quality_handoff_result(
            collection_status="not_requested",
            reason="PR Quality handoff evidence was not requested.",
        )

    summary_display = str(summary_path or "")
    manifest_display = str(manifest_path or "")
    if summary_path is None or manifest_path is None:
        return _pr_quality_handoff_result(
            collection_status="missing",
            reason=(
                "Both PR Quality summary and handoff manifest are required "
                "when either input is requested."
            ),
            summary_path=summary_display,
            manifest_path=manifest_display,
            release_review_blocking=True,
        )

    summary_file = _resolve_input_path(root, summary_path)
    manifest_file = _resolve_input_path(root, manifest_path)
    summary_display = summary_file.as_posix()
    manifest_display = manifest_file.as_posix()

    if not summary_file.is_file() or not manifest_file.is_file():
        missing = [path.as_posix() for path in (summary_file, manifest_file) if not path.is_file()]
        return _pr_quality_handoff_result(
            collection_status="missing",
            reason=f"Requested PR Quality evidence is missing: {missing}",
            summary_path=summary_display,
            manifest_path=manifest_display,
            release_review_blocking=True,
        )

    summary_bytes = summary_file.read_bytes()
    manifest_bytes = manifest_file.read_bytes()
    source_digests = {
        "pr_quality_summary": _sha256_bytes(summary_bytes),
        "pr_quality_handoff_manifest": _sha256_bytes(manifest_bytes),
    }

    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _pr_quality_handoff_result(
            collection_status="malformed",
            reason=f"PR Quality handoff manifest is invalid JSON: {exc}",
            summary_path=summary_display,
            manifest_path=manifest_display,
            release_review_blocking=True,
            source_digests=source_digests,
        )

    if not isinstance(manifest, dict):
        return _pr_quality_handoff_result(
            collection_status="malformed",
            reason="PR Quality handoff manifest must be a JSON object.",
            summary_path=summary_display,
            manifest_path=manifest_display,
            release_review_blocking=True,
            source_digests=source_digests,
        )
    if manifest.get("schema_version") != _PR_QUALITY_HANDOFF_SCHEMA:
        return _pr_quality_handoff_result(
            collection_status="malformed",
            reason="PR Quality handoff manifest schema is unsupported.",
            summary_path=summary_display,
            manifest_path=manifest_display,
            release_review_blocking=True,
            source_digests=source_digests,
        )
    if manifest.get("authority_boundary") != _PR_QUALITY_AUTHORITY_BOUNDARY:
        return _pr_quality_handoff_result(
            collection_status="malformed",
            reason="PR Quality handoff authority boundary is invalid.",
            summary_path=summary_display,
            manifest_path=manifest_display,
            release_review_blocking=True,
            source_digests=source_digests,
        )

    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != 3:
        return _pr_quality_handoff_result(
            collection_status="malformed",
            reason="PR Quality handoff file inventory is invalid.",
            summary_path=summary_display,
            manifest_path=manifest_display,
            release_review_blocking=True,
            source_digests=source_digests,
        )

    normalized_rows: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            return _pr_quality_handoff_result(
                collection_status="malformed",
                reason="PR Quality handoff file row must be an object.",
                summary_path=summary_display,
                manifest_path=manifest_display,
                release_review_blocking=True,
                source_digests=source_digests,
            )
        relative = str(row.get("path", ""))
        if relative in normalized_rows:
            return _pr_quality_handoff_result(
                collection_status="malformed",
                reason=f"PR Quality handoff path is duplicated: {relative}",
                summary_path=summary_display,
                manifest_path=manifest_display,
                release_review_blocking=True,
                source_digests=source_digests,
            )
        normalized_rows[relative] = row

    if set(normalized_rows) != _PR_QUALITY_MANIFEST_PAYLOAD_PATHS:
        return _pr_quality_handoff_result(
            collection_status="malformed",
            reason="PR Quality handoff file allowlist is invalid.",
            summary_path=summary_display,
            manifest_path=manifest_display,
            release_review_blocking=True,
            source_digests=source_digests,
        )

    summary_row = normalized_rows[_PR_QUALITY_SUMMARY_MANIFEST_PATH]
    try:
        expected_size = int(summary_row.get("size_bytes", -1))
    except (TypeError, ValueError):
        expected_size = -1
    expected_digest = str(summary_row.get("sha256", ""))

    if (
        expected_size != len(summary_bytes)
        or expected_digest != source_digests["pr_quality_summary"]
    ):
        return _pr_quality_handoff_result(
            collection_status="digest_mismatch",
            reason=("PR Quality summary bytes do not match the trusted publisher manifest."),
            summary_path=summary_display,
            manifest_path=manifest_display,
            release_review_blocking=True,
            source_digests=source_digests,
        )

    try:
        summary_text = summary_bytes.decode("utf-8")
        decision = _parse_pr_quality_summary(summary_text)
    except (UnicodeDecodeError, ValueError) as exc:
        return _pr_quality_handoff_result(
            collection_status="malformed",
            reason=f"PR Quality summary contract is invalid: {exc}",
            summary_path=summary_display,
            manifest_path=manifest_display,
            release_review_blocking=True,
            source_digests=source_digests,
        )

    head_sha = str(manifest.get("head_sha", ""))
    if head_sha != expected_head_sha:
        return _pr_quality_handoff_result(
            collection_status="stale",
            reason=("PR Quality handoff head does not match the release package head."),
            summary_path=summary_display,
            manifest_path=manifest_display,
            head_sha=head_sha,
            head_matches=False,
            decision=decision,
            release_review_blocking=True,
            source_digests=source_digests,
        )

    release_review_blocking = (
        decision["review_state"] in _PR_QUALITY_BLOCKING_STATES
        or decision["first_blocker"] != "none"
        or decision["required_checks"] != "clear"
        or decision["security_posture"] != "clear"
    )
    return _pr_quality_handoff_result(
        collection_status="collected",
        reason="Trusted PR Quality decision was collected and verified.",
        summary_path=summary_display,
        manifest_path=manifest_display,
        head_sha=head_sha,
        head_matches=True,
        decision=decision,
        release_review_blocking=release_review_blocking,
        source_digests=source_digests,
    )


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_input_bytes(path: Path) -> bytes:
    if not path.is_file():
        return b"missing\0"
    return b"present\0" + path.read_bytes()


def _has(text: str, *needles: str) -> bool:
    lowered = text.lower()
    return all(needle.lower() in lowered for needle in needles)


def _evidence_item(
    *,
    evidence_id: str,
    title: str,
    source: str,
    detected: bool,
    command: str = "",
    human_review_required: bool = True,
) -> JsonObject:
    return {
        "id": evidence_id,
        "title": title,
        "source": source,
        "detected": detected,
        "status": "present" if detected else "missing",
        "command": command,
        "human_review_required": human_review_required,
        "safe_to_publish": False,
        "release_authorized": False,
        "reporting_only": True,
    }


def release_readiness_evidence_input_provenance(
    *,
    repo_root: str | Path = ".",
    current_head_sha: str | None = None,
    generated_at: str | None = None,
    pr_quality_summary: str | Path | None = None,
    pr_quality_handoff_manifest: str | Path | None = None,
) -> JsonObject:
    root = Path(repo_root).resolve()
    data_inputs = {
        relative_path: _read_input_bytes(root / relative_path) for relative_path in _INPUT_PATHS
    }
    input_artifact_schemas: dict[str, str] = {}
    if pr_quality_summary is not None or pr_quality_handoff_manifest is not None:
        data_inputs["pr_quality_summary"] = _optional_input_bytes(
            root,
            pr_quality_summary,
        )
        data_inputs["pr_quality_handoff_manifest"] = _optional_input_bytes(
            root,
            pr_quality_handoff_manifest,
        )
        input_artifact_schemas["pr_quality_handoff_manifest"] = _PR_QUALITY_HANDOFF_SCHEMA

    return build_input_provenance(
        schema_version=SCHEMA_VERSION,
        generator_source=GENERATOR_SOURCE,
        generator_bytes=Path(__file__).read_bytes(),
        data_inputs=data_inputs,
        root=root,
        source_issue_numbers=(),
        source_run_ids=(),
        input_artifact_schemas=input_artifact_schemas,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )


def build_release_readiness_evidence_package(
    repo_root: str | Path = ".",
    *,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
    pr_quality_summary: str | Path | None = None,
    pr_quality_handoff_manifest: str | Path | None = None,
) -> JsonObject:
    root = Path(repo_root).resolve()
    makefile = _read_text(root / "Makefile")
    release_workflow = _read_text(root / ".github/workflows/release.yml")
    release_handoff = _read_text(root / "docs/release-readiness-evidence-handoff.md")
    artifact_reference = _read_text(root / "docs/artifact-reference.md")

    evidence_items = [
        _evidence_item(
            evidence_id="package_build_command",
            title="Package build command",
            source="Makefile/package-validate and .github/workflows/release.yml",
            detected=_has(makefile, "python -m build")
            and _has(release_workflow, "python -m build"),
            command="python -m build",
        ),
        _evidence_item(
            evidence_id="twine_metadata_check",
            title="Twine metadata check",
            source="Makefile/package-validate and .github/workflows/release.yml",
            detected=_has(makefile, "twine check") and _has(release_workflow, "twine check"),
            command="python -m twine check dist/*",
        ),
        _evidence_item(
            evidence_id="wheel_contents_check",
            title="Wheel contents check",
            source="Makefile/package-validate and .github/workflows/release.yml",
            detected=_has(makefile, "check_wheel_contents")
            and _has(release_workflow, "check_wheel_contents"),
            command="python -m check_wheel_contents --ignore W009 dist/*.whl",
        ),
        _evidence_item(
            evidence_id="wheel_smoke_install",
            title="Wheel smoke install",
            source="Makefile/package-validate and .github/workflows/release.yml",
            detected=_has(
                makefile,
                "force-reinstall",
                "dist/*.whl",
                "sdetkit --help",
            )
            and _has(
                release_workflow,
                "force-reinstall",
                "dist/*.whl",
                "sdetkit --help",
            ),
            command=("python -m pip install --force-reinstall dist/*.whl && sdetkit --help"),
        ),
        _evidence_item(
            evidence_id="release_preflight",
            title="Release preflight",
            source="Makefile/release-preflight and .github/workflows/release.yml",
            detected=_has(makefile, "release_preflight.py")
            and _has(release_workflow, "release_preflight.py"),
            command="python scripts/release_preflight.py",
        ),
        _evidence_item(
            evidence_id="release_provenance_attestation",
            title="Release provenance attestation",
            source=".github/workflows/release.yml",
            detected=_has(release_workflow, "attest-build-provenance"),
            command="actions/attest-build-provenance",
        ),
        _evidence_item(
            evidence_id="release_diagnostics_upload",
            title="Release diagnostics upload",
            source=".github/workflows/release.yml",
            detected=_has(
                release_workflow,
                "upload-artifact",
                "release-diagnostics",
            ),
            command=("upload build/release-preflight.json as release diagnostics"),
        ),
        _evidence_item(
            evidence_id="post_publish_or_rollback_plan",
            title="Post-publish or rollback verification plan",
            source=("Makefile/release-verify-plan and docs/release-readiness-evidence-handoff.md"),
            detected=_has(makefile, "release_verify_post_publish.py")
            and (_has(release_handoff, "blocked") or _has(artifact_reference, "release")),
            command="make release-verify-plan",
        ),
    ]

    present_count = sum(1 for item in evidence_items if item["detected"] is True)
    missing = [item for item in evidence_items if item["detected"] is not True]
    provenance = release_readiness_evidence_input_provenance(
        repo_root=root,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
        pr_quality_summary=pr_quality_summary,
        pr_quality_handoff_manifest=pr_quality_handoff_manifest,
    )
    pr_quality_handoff = collect_pr_quality_handoff(
        repo_root=root,
        expected_head_sha=str(provenance.get("generated_from_head_sha", "")),
        summary_path=pr_quality_summary,
        manifest_path=pr_quality_handoff_manifest,
    )
    status = (
        "ready_for_human_release_review"
        if not missing
        and not bool(
            pr_quality_handoff.get(
                "release_review_blocking",
                False,
            )
        )
        else "review_required"
    )

    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit.release_readiness_evidence_package",
        "status": status,
        "report_status": "passed" if not missing else "review_required",
        "reporting_only": True,
        "review_first": True,
        "repo_mutation": False,
        "issue_mutation_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "safe_to_publish": False,
        "release_authorized": False,
        "publish_authorized": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": dict(_AUTHORITY_BOUNDARY),
        "summary": {
            "required_evidence_count": len(evidence_items),
            "present_evidence_count": present_count,
            "missing_evidence_count": len(missing),
            "status": status,
            "next_allowed_action": "human_release_review",
            "pr_quality_collection_status": (pr_quality_handoff["collection_status"]),
            "pr_quality_release_review_blocking": bool(
                pr_quality_handoff["release_review_blocking"]
            ),
        },
        "pr_quality_handoff": pr_quality_handoff,
        "required_human_evidence": list(_REQUIRED_EVIDENCE),
        "blocked_actions": [
            "automatic_release",
            "automatic_publish",
            "automatic_tag_mutation",
            "automatic_security_dismissal",
            "semantic_equivalence_claim",
        ],
        "evidence_items": evidence_items,
        "proof_commands": list(_PROOF_COMMANDS),
        "next_allowed_action": "human_release_review",
    }
    return attach_provenance(payload, provenance)


def check_release_readiness_evidence_freshness(
    *,
    repo_root: str | Path = ".",
    report_path: str | Path = DEFAULT_OUT,
    current_head_sha: str | None = None,
    pr_quality_summary: str | Path | None = None,
    pr_quality_handoff_manifest: str | Path | None = None,
) -> JsonObject:
    current = release_readiness_evidence_input_provenance(
        repo_root=repo_root,
        current_head_sha=current_head_sha,
        pr_quality_summary=pr_quality_summary,
        pr_quality_handoff_manifest=pr_quality_handoff_manifest,
    )
    return check_report_path(
        report_path,
        current,
        expected_schema_version=SCHEMA_VERSION,
    )


def render_release_readiness_evidence_markdown(
    payload: Mapping[str, Any],
) -> str:
    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    lines = [
        "# Release-readiness evidence package",
        "",
        f"- schema_version: `{payload.get('schema_version', 'unknown')}`",
        f"- status: `{payload.get('status', 'unknown')}`",
        f"- generated_at: `{payload.get('generated_at', '')}`",
        f"- current_head_sha: `{payload.get('current_head_sha', '')}`",
        (f"- reporting_only: `{str(bool(payload.get('reporting_only', True))).lower()}`"),
        (f"- review_first: `{str(bool(payload.get('review_first', True))).lower()}`"),
        (f"- safe_to_publish: `{str(bool(payload.get('safe_to_publish', False))).lower()}`"),
        (f"- release_authorized: `{str(bool(payload.get('release_authorized', False))).lower()}`"),
        (f"- next_allowed_action: `{payload.get('next_allowed_action', 'human_release_review')}`"),
        "",
        "## Summary",
        "",
        (f"- required_evidence_count: `{summary.get('required_evidence_count', 0)}`"),
        (f"- present_evidence_count: `{summary.get('present_evidence_count', 0)}`"),
        (f"- missing_evidence_count: `{summary.get('missing_evidence_count', 0)}`"),
        "",
    ]

    handoff = payload.get("pr_quality_handoff", {})
    if not isinstance(handoff, dict):
        handoff = {}
    lines.extend(
        [
            "## PR Quality handoff",
            "",
            (f"- collection_status: `{handoff.get('collection_status', 'not_requested')}`"),
            (f"- available: `{str(bool(handoff.get('available', False))).lower()}`"),
            f"- reason: `{handoff.get('reason', '')}`",
            f"- head_sha: `{handoff.get('head_sha', '')}`",
            (f"- head_matches: `{str(bool(handoff.get('head_matches', False))).lower()}`"),
            f"- review_state: `{handoff.get('review_state', 'unknown')}`",
            f"- first_blocker: `{handoff.get('first_blocker', 'unknown')}`",
            f"- next_action: `{handoff.get('next_action', 'unknown')}`",
            (f"- required_checks: `{handoff.get('required_checks', 'unknown')}`"),
            (f"- security_posture: `{handoff.get('security_posture', 'unknown')}`"),
            (f"- merge_posture: `{handoff.get('merge_posture', 'unknown')}`"),
            (
                "- release_review_blocking: "
                f"`{str(bool(handoff.get('release_review_blocking', False))).lower()}`"
            ),
            f"- summary_path: `{handoff.get('summary_path', '')}`",
            f"- manifest_path: `{handoff.get('manifest_path', '')}`",
            "- reporting_only: `true`",
            "- safe_to_publish: `false`",
            "- release_authorized: `false`",
            "- publish_authorized: `false`",
            "- merge_authorized: `false`",
            "",
            "## Evidence items",
            "",
        ]
    )

    for item in payload.get("evidence_items", []):
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"### {item.get('title', item.get('id', 'unknown'))}",
                f"- id: `{item.get('id', 'unknown')}`",
                f"- status: `{item.get('status', 'unknown')}`",
                f"- source: `{item.get('source', 'unknown')}`",
                f"- command: `{item.get('command', '')}`",
                "- reporting_only: `true`",
                "- safe_to_publish: `false`",
                "- release_authorized: `false`",
                "",
            ]
        )

    lines.extend(["## Proof commands", ""])
    for command in payload.get("proof_commands", []):
        lines.append(f"- `{command}`")

    lines.extend(["", "## Input provenance", ""])
    input_digests = payload.get("input_digests", {})
    if isinstance(input_digests, dict):
        for input_name, digest in sorted(input_digests.items()):
            lines.append(f"- `{input_name}`: `{digest}`")

    lines.extend(["", "## Authority boundary", ""])
    boundary = payload.get("authority_boundary", {})
    if isinstance(boundary, dict):
        for key, value in boundary.items():
            rendered = str(value).lower() if isinstance(value, bool) else value
            lines.append(f"- {key}: `{rendered}`")

    lines.extend(
        [
            "",
            (
                "_Reporting-only. This package does not authorize release, "
                "publish, merge, patch automation, security dismissal, or "
                "semantic-equivalence claims._"
            ),
        ]
    )
    return "\n".join(lines)


def write_release_readiness_evidence_package(
    repo_root: str | Path = ".",
    out_json: str | Path = DEFAULT_OUT,
    out_md: str | Path = DEFAULT_MARKDOWN_OUT,
    *,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
    pr_quality_summary: str | Path | None = None,
    pr_quality_handoff_manifest: str | Path | None = None,
) -> JsonObject:
    payload = build_release_readiness_evidence_package(
        repo_root,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
        pr_quality_summary=pr_quality_summary,
        pr_quality_handoff_manifest=pr_quality_handoff_manifest,
    )
    json_path = Path(out_json)
    md_path = Path(out_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        render_release_readiness_evidence_markdown(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit release-readiness-evidence-package")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-json", default=DEFAULT_OUT)
    parser.add_argument("--out-md", default=DEFAULT_MARKDOWN_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--check-freshness", action="store_true")
    parser.add_argument("--pr-quality-summary")
    parser.add_argument("--pr-quality-handoff-manifest")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.check_freshness:
        freshness = check_release_readiness_evidence_freshness(
            repo_root=args.root,
            report_path=args.out_json,
            pr_quality_summary=args.pr_quality_summary,
            pr_quality_handoff_manifest=(args.pr_quality_handoff_manifest),
        )
        if args.format == "json":
            sys.stdout.write(json.dumps(freshness, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_freshness_text(freshness) + "\n")
        return 0 if freshness["fresh"] else 1

    payload = write_release_readiness_evidence_package(
        repo_root=args.root,
        out_json=args.out_json,
        out_md=args.out_md,
        pr_quality_summary=args.pr_quality_summary,
        pr_quality_handoff_manifest=args.pr_quality_handoff_manifest,
    )

    if args.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_release_readiness_evidence_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
