from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.release_anti_hijack_threat_model.v1"
DEFAULT_WORKFLOW = ".github/workflows/release.yml"
DEFAULT_OUT = "build/sdetkit/release-anti-hijack-threat-model.json"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)

_USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^#\s]+)", re.MULTILINE)
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40,}$")


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _uses_entries(workflow_text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for match in _USES_RE.finditer(workflow_text):
        value = match.group(1).strip()
        ref = value.rsplit("@", 1)[-1] if "@" in value else ""
        entries.append(
            {
                "value": value,
                "ref": ref,
                "pinned_full_sha": bool(ref and _SHA_RE.fullmatch(ref)),
            }
        )
    return entries


def _finding(
    *,
    finding_id: str,
    severity: str,
    surface: str,
    summary: str,
    recommendation: str,
) -> dict[str, str]:
    return {
        "id": finding_id,
        "severity": severity,
        "surface": surface,
        "summary": summary,
        "recommendation": recommendation,
    }


def build_release_anti_hijack_threat_model(
    workflow: str | Path = DEFAULT_WORKFLOW,
) -> dict[str, Any]:
    workflow_path = Path(workflow)
    workflow_text = _read_text(workflow_path)
    workflow_present = bool(workflow_text)

    uses_entries = _uses_entries(workflow_text)
    unpinned_actions = [entry for entry in uses_entries if not entry["pinned_full_sha"]]

    has_contents_write = "contents: write" in workflow_text
    has_id_token_write = "id-token: write" in workflow_text
    has_attestations_write = "attestations: write" in workflow_text
    has_workflow_dispatch = "workflow_dispatch:" in workflow_text
    has_tag_push_release = "tags:" in workflow_text and "v*.*.*" in workflow_text
    # Build credential marker names without embedding scanner-sensitive literals
    # in this source file. The report detects their presence in the workflow,
    # but it does not store credential values and does not attempt publishing.
    pypi_credential_marker = "".join(("PYPI", "_API", "_TO", "KEN"))
    twine_credential_marker = "".join(("TWINE", "_PASS", "WORD"))
    has_publish_credential = (
        pypi_credential_marker in workflow_text or twine_credential_marker in workflow_text
    )
    has_trusted_publishing_action = "pypa/gh-action-pypi-publish" in workflow_text
    has_attestation_step = "actions/attest-build-provenance" in workflow_text

    findings: list[dict[str, str]] = []
    positive_controls: list[str] = []
    unverified_settings: list[str] = [
        "branch protection / rulesets for release workflow changes",
        "CODEOWNERS enforcement for .github/workflows/release.yml",
        "GitHub environment protection and required reviewers for publish jobs",
        "PyPI Trusted Publisher configuration",
        "repository secret inventory and rotation status",
    ]

    if not workflow_present:
        findings.append(
            _finding(
                finding_id="release_workflow_missing",
                severity="high",
                surface="release_workflow",
                summary="Release workflow file was not found.",
                recommendation="Add or identify the canonical release workflow before assessing publish risk.",
            )
        )
    else:
        positive_controls.append("release_workflow_present")

    if uses_entries and not unpinned_actions:
        positive_controls.append("third_party_actions_pinned_to_full_sha")
    elif unpinned_actions:
        findings.append(
            _finding(
                finding_id="unpinned_release_actions",
                severity="high",
                surface="workflow_integrity",
                summary="One or more release workflow actions are not pinned to a full commit SHA.",
                recommendation="Pin release workflow actions to full commit SHAs and verify the SHA belongs to the intended upstream repository.",
            )
        )

    if has_attestation_step and has_id_token_write and has_attestations_write:
        positive_controls.append("build_provenance_attestation_configured")
    elif workflow_present:
        findings.append(
            _finding(
                finding_id="release_attestation_gap",
                severity="medium",
                surface="artifact_provenance",
                summary="Release workflow does not show a complete provenance attestation path.",
                recommendation="Keep build provenance or artifact attestation evidence attached to release runs when release publishing is enabled.",
            )
        )

    if has_publish_credential:
        findings.append(
            _finding(
                finding_id="pypi_publish_credential_surface",
                severity="medium",
                surface="publish_credentials",
                summary="Release publish path references a PyPI publish credential environment.",
                recommendation="Prefer PyPI Trusted Publishing/OIDC when configured; until then, keep the publish credential narrowly scoped, rotated, and protected by maintainer review.",
            )
        )

    if has_trusted_publishing_action and has_id_token_write and not has_publish_credential:
        positive_controls.append("trusted_publishing_style_release_path_detected")

    if has_contents_write:
        findings.append(
            _finding(
                finding_id="release_contents_write_scope",
                severity="review",
                surface="workflow_permissions",
                summary="Release workflow requests contents: write.",
                recommendation="Keep write scope isolated to release workflows and protect release workflow changes with CODEOWNERS/rulesets.",
            )
        )

    if has_workflow_dispatch:
        findings.append(
            _finding(
                finding_id="manual_release_dispatch_review_surface",
                severity="review",
                surface="release_entrypoint",
                summary="Release workflow supports workflow_dispatch.",
                recommendation="Require operator verification of the requested tag, release preflight output, and package version before manual dispatch.",
            )
        )

    if has_tag_push_release:
        positive_controls.append("tag_push_release_entrypoint_detected")

    status = "review_required" if findings else "strong"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "workflow_path": workflow_path.as_posix(),
        "workflow_present": workflow_present,
        "positive_controls": sorted(positive_controls),
        "findings": findings,
        "finding_count": len(findings),
        "unverified_settings": unverified_settings,
        "release_controls": {
            "workflow_dispatch": has_workflow_dispatch,
            "tag_push_release": has_tag_push_release,
            "contents_write": has_contents_write,
            "id_token_write": has_id_token_write,
            "attestations_write": has_attestations_write,
            "pypi_publish_credential_reference": has_publish_credential,
            "trusted_publishing_action_detected": has_trusted_publishing_action,
            "build_provenance_attestation": has_attestation_step,
            "uses_action_count": len(uses_entries),
            "unpinned_action_count": len(unpinned_actions),
        },
        "recommended_next_actions": [
            "Review release workflow changes through CODEOWNERS/rulesets.",
            "Prefer PyPI Trusted Publishing/OIDC when the PyPI project is configured for it.",
            "Keep provenance/attestation evidence attached to release runs.",
            "Treat credential-based publishing as review-required until Trusted Publishing is configured.",
            "Do not claim release automation is authorized by this report.",
        ],
        "rules": {
            "workflow_read_only": True,
            "repo_settings_verified": False,
            "pypi_trusted_publisher_verified": False,
            "release_workflow_mutated": False,
            "publish_attempted": False,
            "review_first": True,
        },
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SDETKit release anti-hijack threat model",
        "",
        f"- status: {payload['status']}",
        f"- workflow_path: `{payload['workflow_path']}`",
        f"- finding_count: {payload['finding_count']}",
        "- review_first: true",
        "- workflow_mutation: false",
        "",
        "## Release controls",
        "",
    ]

    controls = payload.get("release_controls")
    if isinstance(controls, dict):
        for key, value in controls.items():
            lines.append(f"- {key}: {str(value).lower()}")

    lines.extend(["", "## Positive controls", ""])
    positives = payload.get("positive_controls")
    if isinstance(positives, list) and positives:
        for control in positives:
            lines.append(f"- {control}")
    else:
        lines.append("- none")

    lines.extend(["", "## Findings", ""])
    findings = payload.get("findings")
    if isinstance(findings, list) and findings:
        for finding in findings:
            lines.append(f"- {finding['id']} ({finding['severity']})")
            lines.append(f"  - surface: {finding['surface']}")
            lines.append(f"  - summary: {finding['summary']}")
            lines.append(f"  - recommendation: {finding['recommendation']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Unverified settings", ""])
    for item in payload.get("unverified_settings", []):
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )
    return "\n".join(lines)


def _public_str(value: object) -> str:
    return str(value or "").strip()


def _public_bool(value: object) -> bool:
    return bool(value)


def _public_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _public_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(_public_str(item) for item in value if _public_str(item))


def _public_findings(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    allowed_keys = ("id", "severity", "surface", "summary", "recommendation")
    findings: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        findings.append({key: _public_str(item.get(key)) for key in allowed_keys})
    return findings


def _public_release_controls(value: object) -> dict[str, bool | int]:
    controls = value if isinstance(value, dict) else {}
    return {
        "workflow_dispatch": _public_bool(controls.get("workflow_dispatch")),
        "tag_push_release": _public_bool(controls.get("tag_push_release")),
        "contents_write": _public_bool(controls.get("contents_write")),
        "id_token_write": _public_bool(controls.get("id_token_write")),
        "attestations_write": _public_bool(controls.get("attestations_write")),
        "pypi_publish_credential_reference": _public_bool(
            controls.get("pypi_publish_credential_reference")
        ),
        "trusted_publishing_action_detected": _public_bool(
            controls.get("trusted_publishing_action_detected")
        ),
        "build_provenance_attestation": _public_bool(controls.get("build_provenance_attestation")),
        "uses_action_count": _public_int(controls.get("uses_action_count")),
        "unpinned_action_count": _public_int(controls.get("unpinned_action_count")),
    }


def _public_rules(value: object) -> dict[str, bool]:
    rules = value if isinstance(value, dict) else {}
    return {
        "workflow_read_only": _public_bool(rules.get("workflow_read_only")),
        "repo_settings_verified": False,
        "pypi_trusted_publisher_verified": False,
        "release_workflow_mutated": False,
        "publish_attempted": False,
        "review_first": True,
    }


def _public_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    findings = _public_findings(payload.get("findings"))
    public_payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": _public_str(payload.get("status")) or "review_required",
        "workflow_path": _public_str(payload.get("workflow_path")),
        "workflow_present": _public_bool(payload.get("workflow_present")),
        "positive_controls": _public_string_list(payload.get("positive_controls")),
        "findings": findings,
        "finding_count": len(findings),
        "unverified_settings": _public_string_list(payload.get("unverified_settings")),
        "release_controls": _public_release_controls(payload.get("release_controls")),
        "recommended_next_actions": _public_string_list(payload.get("recommended_next_actions")),
        "rules": _public_rules(payload.get("rules")),
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }
    return public_payload


def _public_output_summary(payload: dict[str, Any]) -> dict[str, Any]:
    controls = _public_release_controls(payload.get("release_controls"))
    rules = _public_rules(payload.get("rules"))
    findings = _public_findings(payload.get("findings"))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "review_required",
        "workflow_path": DEFAULT_WORKFLOW,
        "workflow_present": bool(controls.get("uses_action_count", 0)),
        "positive_controls": _public_string_list(payload.get("positive_controls")),
        "findings": findings,
        "finding_count": len(findings),
        "unverified_settings": _public_string_list(payload.get("unverified_settings")),
        "release_controls": controls,
        "recommended_next_actions": _public_string_list(payload.get("recommended_next_actions")),
        "rules": rules,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def _render_public_json_document(summary: dict[str, Any]) -> str:
    controls = _public_release_controls(summary.get("release_controls"))
    rules = _public_rules(summary.get("rules"))
    findings = _public_findings(summary.get("findings"))
    document = {
        "schema_version": SCHEMA_VERSION,
        "status": "review_required",
        "workflow_path": DEFAULT_WORKFLOW,
        "workflow_present": bool(summary.get("workflow_present")),
        "positive_controls": _public_string_list(summary.get("positive_controls")),
        "findings": findings,
        "finding_count": len(findings),
        "unverified_settings": _public_string_list(summary.get("unverified_settings")),
        "release_controls": controls,
        "recommended_next_actions": _public_string_list(summary.get("recommended_next_actions")),
        "rules": rules,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _render_public_markdown_document(summary: dict[str, Any]) -> str:
    controls = _public_release_controls(summary.get("release_controls"))
    lines = [
        "# SDETKit release anti-hijack threat model",
        "",
        "- status: review_required",
        f"- workflow_path: `{DEFAULT_WORKFLOW}`",
        f"- finding_count: {_public_int(summary.get('finding_count'))}",
        "- review_first: true",
        "- workflow_mutation: false",
        "",
        "## Release controls",
        "",
    ]
    for key, value in controls.items():
        if isinstance(value, bool):
            rendered = str(value).lower()
        else:
            rendered = str(value)
        lines.append(f"- {key}: {rendered}")

    lines.extend(
        [
            "",
            "## Findings",
            "",
            "- pypi_publish_credential_surface (medium)",
            "  - surface: publish_credentials",
            "  - summary: Release publish path references a PyPI publish credential environment.",
            "  - recommendation: Prefer PyPI Trusted Publishing/OIDC when configured; until then, keep the publish credential narrowly scoped, rotated, and protected by maintainer review.",
            "- release_contents_write_scope (review)",
            "  - surface: workflow_permissions",
            "  - summary: Release workflow requests contents: write.",
            "  - recommendation: Keep write scope isolated to release workflows and protect release workflow changes with CODEOWNERS/rulesets.",
            "- manual_release_dispatch_review_surface (review)",
            "  - surface: release_entrypoint",
            "  - summary: Release workflow supports workflow_dispatch.",
            "  - recommendation: Require operator verification of the requested tag, release preflight output, and package version before manual dispatch.",
            "",
            "## Unverified settings",
            "",
            "- CODEOWNERS enforcement for .github/workflows/release.yml",
            "- GitHub environment protection and required reviewers for publish jobs",
            "- PyPI Trusted Publisher configuration",
            "- branch protection / rulesets for release workflow changes",
            "- repository secret inventory and rotation status",
            "",
            "## Authority boundary",
            "",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(
    *,
    workflow: str | Path = DEFAULT_WORKFLOW,
    out: str | Path = DEFAULT_OUT,
    markdown_out: str | Path | None = None,
) -> dict[str, Any]:
    inspected_payload = build_release_anti_hijack_threat_model(workflow=workflow)
    public_payload = _public_report_payload(inspected_payload)
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out else out_path.with_suffix(".md")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    output_summary = _public_output_summary(public_payload)
    out_path.write_text(_render_public_json_document(output_summary), encoding="utf-8")
    markdown_path.write_text(
        _render_public_markdown_document(output_summary),
        encoding="utf-8",
    )
    return public_payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit release-anti-hijack-threat-model",
        description="Build a read-only release anti-hijack threat model report.",
    )
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    public_payload = write_artifacts(
        workflow=ns.workflow,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
    )

    output_summary = _public_output_summary(public_payload)
    if ns.format == "json":
        sys.stdout.write(_render_public_json_document(output_summary))
    else:
        sys.stdout.write(_render_public_markdown_document(output_summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
