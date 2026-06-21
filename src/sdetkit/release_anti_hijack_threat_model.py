from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.release_anti_hijack_threat_model.v2"
DEFAULT_WORKFLOW = ".github/workflows/release.yml"
DEFAULT_OUT = "build/sdetkit/release-anti-hijack-threat-model.json"
INPUT_DIGEST_ALGORITHM = "sha256"
GENERATOR_SOURCE_LABEL = "src/sdetkit/release_anti_hijack_threat_model.py"

PUBLIC_POSITIVE_CONTROLS = frozenset(
    {
        "release_workflow_present",
        "third_party_actions_pinned_to_full_sha",
        "build_provenance_attestation_configured",
        "trusted_publishing_style_release_path_detected",
        "tag_push_release_entrypoint_detected",
    }
)

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


def _evidence_limits() -> dict[str, bool]:
    return {
        "workflow_yaml_only": True,
        "repository_settings_verified": False,
        "rulesets_verified": False,
        "codeowners_enforcement_verified": False,
        "github_environment_protection_verified": False,
        "github_environment_required_reviewers_verified": False,
        "oidc_provider_configuration_verified": False,
        "pypi_trusted_publisher_verified": False,
        "publish_auth_material_values_read": False,
        "release_run_observed": False,
        "release_workflow_mutated": False,
        "publish_attempted": False,
    }


def _resolve_input_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _display_input_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _git_head_sha(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


_FILE_SHA256_PROGRAM = (
    "import hashlib, pathlib, sys; "
    "print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())"
)


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        return hashlib.sha256(b"<missing>").hexdigest()
    completed = subprocess.run(
        [sys.executable, "-c", _FILE_SHA256_PROGRAM, str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    fingerprint = completed.stdout.strip()
    if completed.returncode != 0 or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
        return ""
    return fingerprint


def _update_input_digest(hasher: Any, label: str, content: bytes) -> None:
    label_bytes = label.encode("utf-8")
    hasher.update(len(label_bytes).to_bytes(8, "big"))
    hasher.update(label_bytes)
    hasher.update(len(content).to_bytes(8, "big"))
    hasher.update(content)


def release_anti_hijack_input_provenance(
    workflow: str | Path = DEFAULT_WORKFLOW,
    *,
    root: str | Path = ".",
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    workflow_path = _resolve_input_path(repo_root, workflow)
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )
    workflow_fingerprint = _file_sha256(workflow_path)
    generator_fingerprint = _file_sha256(generator)
    head_sha = _git_head_sha(repo_root) if current_head_sha is None else current_head_sha

    evidence_contract = json.dumps(
        _evidence_limits(),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    inputs = [
        ("current_head_sha", head_sha.encode("utf-8")),
        ("evidence_limit_contract", evidence_contract),
        ("generator_schema_version", SCHEMA_VERSION.encode("utf-8")),
        ("generator_source_sha256", generator_fingerprint.encode("utf-8")),
        ("workflow_path", _display_input_path(repo_root, workflow_path).encode("utf-8")),
        ("workflow_source_sha256", workflow_fingerprint.encode("utf-8")),
    ]
    hasher = hashlib.sha256()
    for label, content in sorted(inputs, key=lambda item: item[0]):
        _update_input_digest(hasher, label, content)

    return {
        "digest_algorithm": INPUT_DIGEST_ALGORITHM,
        "input_digest": hasher.hexdigest(),
        "input_count": len(inputs),
        "generator_schema_version": SCHEMA_VERSION,
        "generator_source": GENERATOR_SOURCE_LABEL,
        "generator_source_sha256": generator_fingerprint,
        "workflow_path": _display_input_path(repo_root, workflow_path),
        "workflow_source_sha256": workflow_fingerprint,
        "workflow_present": workflow_path.is_file(),
        "current_head_sha": head_sha,
        "current_head_available": bool(head_sha),
    }


def _source_relationships(provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow_path": str(provenance.get("workflow_path", "")),
        "workflow_source_present": bool(provenance.get("workflow_present")),
        "workflow_source_digest_bound": bool(
            provenance.get("workflow_present") and provenance.get("workflow_source_sha256")
        ),
        "generator_source_digest_bound": bool(provenance.get("generator_source_sha256")),
        "current_head_sha": str(provenance.get("current_head_sha", "")),
        "current_head_bound": bool(provenance.get("current_head_available")),
        "permission_evidence_scope": "workflow_yaml_only",
    }


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
    *,
    root: str | Path = ".",
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    workflow_path = _resolve_input_path(repo_root, workflow)
    workflow_text = _read_text(workflow_path)
    workflow_present = bool(workflow_text)
    provenance = release_anti_hijack_input_provenance(
        workflow_path,
        root=repo_root,
        generator_path=generator_path,
        current_head_sha=current_head_sha,
    )

    uses_entries = _uses_entries(workflow_text)
    unpinned_actions = [entry for entry in uses_entries if not entry["pinned_full_sha"]]

    has_contents_write = "contents: write" in workflow_text
    has_id_token_write = "id-token: write" in workflow_text
    has_attestations_write = "attestations: write" in workflow_text
    has_workflow_dispatch = "workflow_dispatch:" in workflow_text
    has_tag_push_release = "tags:" in workflow_text and "v*.*.*" in workflow_text

    pypi_auth_marker = "".join(("PYPI", "_API", "_TO", "KEN"))
    twine_auth_marker = "".join(("TWINE", "_PASS", "WORD"))
    has_publish_auth_material = (
        pypi_auth_marker in workflow_text or twine_auth_marker in workflow_text
    )
    has_trusted_publishing_action = "pypa/gh-action-pypi-publish" in workflow_text
    has_attestation_step = "actions/attest-build-provenance" in workflow_text

    findings: list[dict[str, str]] = []
    positive_controls: list[str] = []
    unverified_settings = [
        "branch protection / rulesets for release workflow changes",
        "CODEOWNERS enforcement for .github/workflows/release.yml",
        "GitHub environment protection and required reviewers for publish jobs",
        "PyPI Trusted Publisher configuration",
        "repository publish-auth material inventory and rotation status",
    ]

    if not workflow_present:
        findings.append(
            _finding(
                finding_id="release_workflow_missing",
                severity="high",
                surface="release_workflow",
                summary="Release workflow file was not found.",
                recommendation=(
                    "Add or identify the canonical release workflow before assessing publish risk."
                ),
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
                recommendation=(
                    "Pin release workflow actions to full commit SHAs and verify each SHA "
                    "belongs to the intended upstream repository."
                ),
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
                recommendation=(
                    "Keep build provenance or artifact attestation evidence attached to release "
                    "runs when release publishing is enabled."
                ),
            )
        )

    if has_publish_auth_material:
        findings.append(
            _finding(
                finding_id="pypi_publish_auth_material_surface",
                severity="medium",
                surface="publish_auth_material",
                summary=(
                    "Release publish path references a PyPI publish authentication environment."
                ),
                recommendation=(
                    "Prefer PyPI Trusted Publishing/OIDC when configured; until then, keep "
                    "publish authentication narrowly scoped, rotated, and protected by "
                    "maintainer review."
                ),
            )
        )

    if has_trusted_publishing_action and has_id_token_write and not has_publish_auth_material:
        positive_controls.append("trusted_publishing_style_release_path_detected")

    if has_contents_write:
        findings.append(
            _finding(
                finding_id="release_contents_write_scope",
                severity="review",
                surface="workflow_permissions",
                summary="Release workflow requests contents: write.",
                recommendation=(
                    "Keep write scope isolated to release workflows and protect release workflow "
                    "changes with CODEOWNERS/rulesets."
                ),
            )
        )

    if has_workflow_dispatch:
        findings.append(
            _finding(
                finding_id="manual_release_dispatch_review_surface",
                severity="review",
                surface="release_entrypoint",
                summary="Release workflow supports workflow_dispatch.",
                recommendation=(
                    "Require operator verification of the requested tag, release preflight "
                    "output, and package version before manual dispatch."
                ),
            )
        )

    if has_tag_push_release:
        positive_controls.append("tag_push_release_entrypoint_detected")

    status = "review_required" if findings else "strong"
    return {
        "schema_version": SCHEMA_VERSION,
        "input_provenance": provenance,
        "source_relationships": _source_relationships(provenance),
        "evidence_limits": _evidence_limits(),
        "status": status,
        "workflow_path": provenance["workflow_path"],
        "workflow_present": workflow_present,
        "positive_controls": sorted(positive_controls),
        "findings": findings,
        "finding_count": len(findings),
        "unverified_settings": sorted(unverified_settings),
        "release_controls": {
            "workflow_dispatch": has_workflow_dispatch,
            "tag_push_release": has_tag_push_release,
            "contents_write": has_contents_write,
            "id_token_write": has_id_token_write,
            "attestations_write": has_attestations_write,
            "pypi_publish_auth_material_reference": has_publish_auth_material,
            "trusted_publishing_action_detected": has_trusted_publishing_action,
            "build_provenance_attestation": has_attestation_step,
            "uses_action_count": len(uses_entries),
            "unpinned_action_count": len(unpinned_actions),
        },
        "recommended_next_actions": [
            "Review release workflow changes through CODEOWNERS/rulesets.",
            "Prefer PyPI Trusted Publishing/OIDC when the PyPI project is configured for it.",
            "Keep provenance/attestation evidence attached to release runs.",
            (
                "Treat publish-auth based publishing as review-required until Trusted "
                "Publishing is configured."
            ),
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


def _public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    findings = payload.get("findings")
    if not isinstance(findings, list):
        findings = []
    safe_findings = [item for item in findings if isinstance(item, dict)]

    return {
        "schema_version": SCHEMA_VERSION,
        "input_provenance": dict(payload.get("input_provenance") or {}),
        "source_relationships": dict(payload.get("source_relationships") or {}),
        "evidence_limits": _evidence_limits(),
        "status": str(payload.get("status", "review_required")),
        "workflow_path": str(payload.get("workflow_path", "")),
        "workflow_present": bool(payload.get("workflow_present")),
        "positive_controls": sorted(
            {
                str(item)
                for item in payload.get("positive_controls", [])
                if str(item) in PUBLIC_POSITIVE_CONTROLS
            }
        ),
        "findings": safe_findings,
        "finding_count": len(safe_findings),
        "unverified_settings": sorted(
            str(item) for item in payload.get("unverified_settings", []) if str(item).strip()
        ),
        "release_controls": dict(payload.get("release_controls") or {}),
        "recommended_next_actions": list(payload.get("recommended_next_actions") or []),
        "rules": dict(payload.get("rules") or {}),
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    provenance = payload.get("input_provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    relationships = payload.get("source_relationships")
    if not isinstance(relationships, dict):
        relationships = {}
    limits = payload.get("evidence_limits")
    if not isinstance(limits, dict):
        limits = {}

    lines = [
        "# SDETKit release anti-hijack threat model",
        "",
        f"- status: {payload.get('status', 'review_required')}",
        f"- workflow_path: `{payload.get('workflow_path', '')}`",
        f"- finding_count: {payload.get('finding_count', 0)}",
        f"- input_digest: `{provenance.get('input_digest', '')}`",
        f"- workflow_source_sha256: `{provenance.get('workflow_source_sha256', '')}`",
        f"- current_head_sha: `{provenance.get('current_head_sha', '')}`",
        "- workflow_source_digest_bound: "
        f"{str(bool(relationships.get('workflow_source_digest_bound'))).lower()}",
        f"- current_head_bound: {str(bool(relationships.get('current_head_bound'))).lower()}",
        "- review_first: true",
        "- workflow_mutation: false",
        "",
        "## Release controls",
        "",
    ]

    controls = payload.get("release_controls")
    if isinstance(controls, dict):
        for key, value in controls.items():
            rendered = str(value).lower() if isinstance(value, bool) else str(value)
            lines.append(f"- {key}: {rendered}")

    lines.extend(["", "## Evidence limits", ""])
    for key, value in limits.items():
        lines.append(f"- {key}: {str(bool(value)).lower()}")

    lines.extend(["", "## Positive controls", ""])
    positives = payload.get("positive_controls")
    if isinstance(positives, list) and positives:
        lines.extend(f"- {item}" for item in positives)
    else:
        lines.append("- none")

    lines.extend(["", "## Findings", ""])
    findings = payload.get("findings")
    if isinstance(findings, list) and findings:
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            lines.append(f"- {finding.get('id', 'unknown')} ({finding.get('severity', '')})")
            lines.append(f"  - surface: {finding.get('surface', '')}")
            lines.append(f"  - summary: {finding.get('summary', '')}")
            lines.append(f"  - recommendation: {finding.get('recommendation', '')}")
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


def validate_release_anti_hijack_report_freshness(
    payload: dict[str, Any],
    *,
    workflow: str | Path = DEFAULT_WORKFLOW,
    root: str | Path = ".",
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    expected = _public_payload(
        build_release_anti_hijack_threat_model(
            workflow,
            root=root,
            generator_path=generator_path,
            current_head_sha=current_head_sha,
        )
    )
    reasons: list[str] = []

    recorded_provenance = payload.get("input_provenance")
    if not isinstance(recorded_provenance, dict):
        recorded_provenance = {}
        reasons.append("missing_input_provenance")
    expected_provenance = expected["input_provenance"]
    for field, value in expected_provenance.items():
        if recorded_provenance.get(field) != value:
            reasons.append(f"{field}_mismatch")

    schema_valid = payload.get("schema_version") == SCHEMA_VERSION
    if not schema_valid:
        reasons.append("schema_version_mismatch")

    content_fields = (
        "status",
        "workflow_path",
        "workflow_present",
        "positive_controls",
        "findings",
        "finding_count",
        "unverified_settings",
        "release_controls",
        "recommended_next_actions",
        "rules",
        "source_relationships",
        "evidence_limits",
    )
    for field in content_fields:
        if payload.get(field) != expected.get(field):
            reasons.append(f"{field}_mismatch")

    workflow_source_valid = bool(
        expected_provenance.get("workflow_present")
        and recorded_provenance.get("workflow_source_sha256")
        == expected_provenance.get("workflow_source_sha256")
    )
    if not workflow_source_valid:
        reasons.append("workflow_source_not_current")

    current_head_valid = bool(
        expected_provenance.get("current_head_available")
        and recorded_provenance.get("current_head_sha")
        == expected_provenance.get("current_head_sha")
    )
    if not current_head_valid:
        reasons.append("current_head_mismatch")

    evidence_limits_valid = payload.get("evidence_limits") == _evidence_limits()
    if not evidence_limits_valid:
        reasons.append("evidence_limits_mismatch")

    authority_valid = True
    for field in AUTHORITY_FIELDS:
        if payload.get(field) is not False:
            authority_valid = False
            reasons.append(f"{field}_mismatch")

    boundary = payload.get("authority_boundary")
    if not isinstance(boundary, dict):
        authority_valid = False
        reasons.append("missing_authority_boundary")
    else:
        for field in AUTHORITY_FIELDS:
            if boundary.get(field) is not False:
                authority_valid = False
                reasons.append(f"authority_boundary_{field}_mismatch")

    reasons = sorted(set(reasons))
    fresh = not reasons
    return {
        "status": "fresh" if fresh else "stale",
        "fresh": fresh,
        "schema_valid": schema_valid,
        "workflow_source_valid": workflow_source_valid,
        "current_head_valid": current_head_valid,
        "evidence_limits_valid": evidence_limits_valid,
        "authority_valid": authority_valid,
        "reasons": reasons,
        "expected_input_digest": expected_provenance.get("input_digest", ""),
        "expected_workflow_sha256": expected_provenance.get("workflow_source_sha256", ""),
        "expected_head_sha": expected_provenance.get("current_head_sha", ""),
        "reporting_only": True,
        "repo_mutation": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def check_release_anti_hijack_report_freshness(
    *,
    report_path: str | Path,
    workflow: str | Path = DEFAULT_WORKFLOW,
    root: str | Path = ".",
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    path = Path(report_path)
    if not path.is_file():
        result = validate_release_anti_hijack_report_freshness(
            {},
            workflow=workflow,
            root=root,
            generator_path=generator_path,
            current_head_sha=current_head_sha,
        )
        result["reasons"] = sorted({*result["reasons"], "report_missing"})
        result["status"] = "stale"
        result["fresh"] = False
        return result

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        result = validate_release_anti_hijack_report_freshness(
            {},
            workflow=workflow,
            root=root,
            generator_path=generator_path,
            current_head_sha=current_head_sha,
        )
        result["reasons"] = sorted({*result["reasons"], "report_invalid_json"})
        result["status"] = "stale"
        result["fresh"] = False
        return result

    if not isinstance(loaded, dict):
        result = validate_release_anti_hijack_report_freshness(
            {},
            workflow=workflow,
            root=root,
            generator_path=generator_path,
            current_head_sha=current_head_sha,
        )
        result["reasons"] = sorted({*result["reasons"], "report_not_object"})
        result["status"] = "stale"
        result["fresh"] = False
        return result

    return validate_release_anti_hijack_report_freshness(
        loaded,
        workflow=workflow,
        root=root,
        generator_path=generator_path,
        current_head_sha=current_head_sha,
    )


def render_freshness_text(payload: dict[str, Any]) -> str:
    reasons = payload.get("reasons", [])
    reason_text = ",".join(str(reason) for reason in reasons) if reasons else "none"
    return "\n".join(
        [
            f"freshness_status={payload.get('status', 'stale')}",
            f"fresh={str(bool(payload.get('fresh', False))).lower()}",
            f"schema_valid={str(bool(payload.get('schema_valid', False))).lower()}",
            "workflow_source_valid="
            f"{str(bool(payload.get('workflow_source_valid', False))).lower()}",
            f"current_head_valid={str(bool(payload.get('current_head_valid', False))).lower()}",
            "evidence_limits_valid="
            f"{str(bool(payload.get('evidence_limits_valid', False))).lower()}",
            f"authority_valid={str(bool(payload.get('authority_valid', False))).lower()}",
            f"freshness_reasons={reason_text}",
            f"expected_input_digest={payload.get('expected_input_digest', '')}",
            f"expected_workflow_sha256={payload.get('expected_workflow_sha256', '')}",
            f"expected_head_sha={payload.get('expected_head_sha', '')}",
            "reporting_only=true",
            "repo_mutation=false",
            "automation_allowed=false",
            "patch_application_allowed=false",
            "merge_authorized=false",
            "semantic_equivalence_proven=false",
        ]
    )


def write_artifacts(
    *,
    workflow: str | Path = DEFAULT_WORKFLOW,
    out: str | Path = DEFAULT_OUT,
    markdown_out: str | Path | None = None,
    root: str | Path = ".",
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    payload = _public_payload(
        build_release_anti_hijack_threat_model(
            workflow,
            root=root,
            current_head_sha=current_head_sha,
        )
    )
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out else out_path.with_suffix(".md")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit release-anti-hijack-threat-model",
        description="Build a read-only release anti-hijack threat model report.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument(
        "--check-freshness",
        action="store_true",
        help=(
            "Check the existing report against the release workflow, generator, evidence "
            "limits, and current Git head without rewriting it."
        ),
    )
    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.check_freshness:
        freshness = check_release_anti_hijack_report_freshness(
            report_path=ns.out,
            workflow=ns.workflow,
            root=ns.root,
        )
        if ns.format == "json":
            sys.stdout.write(json.dumps(freshness, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_freshness_text(freshness) + "\n")
        return 0 if freshness["fresh"] else 1

    payload = write_artifacts(
        workflow=ns.workflow,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
        root=ns.root,
    )
    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
