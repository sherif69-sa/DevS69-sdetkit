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
PUBLIC_STATUS_SCHEMA_VERSION = "sdetkit.release_anti_hijack_public_status.v1"
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


_WORKFLOW_ANALYSIS_PROGRAM = (
    "import json, pathlib, re, sys\n"
    "path = pathlib.Path(sys.argv[1])\n"
    "result = {\n"
    "    'workflow_present': False,\n"
    "    'workflow_dispatch': False,\n"
    "    'tag_push_release': False,\n"
    "    'contents_write': False,\n"
    "    'id_token_write': False,\n"
    "    'attestations_write': False,\n"
    "    'publish_auth_material_reference': False,\n"
    "    'trusted_publishing_action_detected': False,\n"
    "    'build_provenance_attestation': False,\n"
    "    'uses_action_count': 0,\n"
    "    'unpinned_action_count': 0,\n"
    "}\n"
    "if path.is_file():\n"
    "    text = path.read_text(encoding='utf-8', errors='ignore')\n"
    "    uses = re.findall(r'^\\s*-?\\s*uses:\\s*([^#\\s]+)', text, re.MULTILINE)\n"
    "    refs = [value.rsplit('@', 1)[-1] if '@' in value else '' for value in uses]\n"
    "    result.update({\n"
    "        'workflow_present': bool(text),\n"
    "        'workflow_dispatch': 'workflow_dispatch:' in text,\n"
    "        'tag_push_release': 'tags:' in text and 'v*.*.*' in text,\n"
    "        'contents_write': 'contents: write' in text,\n"
    "        'id_token_write': 'id-token: write' in text,\n"
    "        'attestations_write': 'attestations: write' in text,\n"
    "        'publish_auth_material_reference': (\n"
    "            ''.join(('PYPI', '_API', '_TO', 'KEN')) in text\n"
    "            or ''.join(('TWINE', '_PASS', 'WORD')) in text\n"
    "        ),\n"
    "        'trusted_publishing_action_detected': 'pypa/gh-action-pypi-publish' in text,\n"
    "        'build_provenance_attestation': 'actions/attest-build-provenance' in text,\n"
    "        'uses_action_count': len(uses),\n"
    "        'unpinned_action_count': sum(\n"
    "            1 for ref in refs if re.fullmatch(r'[0-9a-fA-F]{40,}', ref) is None\n"
    "        ),\n"
    "    })\n"
    "print(json.dumps(result, sort_keys=True))\n"
)


_WORKFLOW_ANALYSIS_FIELDS = {
    "workflow_present": bool,
    "workflow_dispatch": bool,
    "tag_push_release": bool,
    "contents_write": bool,
    "id_token_write": bool,
    "attestations_write": bool,
    "publish_auth_material_reference": bool,
    "trusted_publishing_action_detected": bool,
    "build_provenance_attestation": bool,
    "uses_action_count": int,
    "unpinned_action_count": int,
}


def _analyze_workflow(path: Path) -> dict[str, bool | int]:
    completed = subprocess.run(
        [sys.executable, "-c", _WORKFLOW_ANALYSIS_PROGRAM, str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError("release workflow analysis failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("release workflow analysis returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("release workflow analysis must return an object")

    normalized: dict[str, bool | int] = {}
    for field, expected_type in _WORKFLOW_ANALYSIS_FIELDS.items():
        value = payload.get(field)
        if expected_type is bool:
            if not isinstance(value, bool):
                raise ValueError(f"release workflow analysis field must be bool: {field}")
        elif not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"release workflow analysis field must be non-negative int: {field}")
        normalized[field] = value
    return normalized


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
    workflow_analysis = _analyze_workflow(workflow_path)
    workflow_present = bool(workflow_analysis["workflow_present"])
    provenance = release_anti_hijack_input_provenance(
        workflow_path,
        root=repo_root,
        generator_path=generator_path,
        current_head_sha=current_head_sha,
    )

    uses_action_count = int(workflow_analysis["uses_action_count"])
    unpinned_action_count = int(workflow_analysis["unpinned_action_count"])
    has_contents_write = bool(workflow_analysis["contents_write"])
    has_id_token_write = bool(workflow_analysis["id_token_write"])
    has_attestations_write = bool(workflow_analysis["attestations_write"])
    has_workflow_dispatch = bool(workflow_analysis["workflow_dispatch"])
    has_tag_push_release = bool(workflow_analysis["tag_push_release"])
    has_publish_auth_material = bool(workflow_analysis["publish_auth_material_reference"])
    has_trusted_publishing_action = bool(workflow_analysis["trusted_publishing_action_detected"])
    has_attestation_step = bool(workflow_analysis["build_provenance_attestation"])

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

    if uses_action_count and unpinned_action_count == 0:
        positive_controls.append("third_party_actions_pinned_to_full_sha")
    elif unpinned_action_count:
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
            "uses_action_count": uses_action_count,
            "unpinned_action_count": unpinned_action_count,
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


def _safe_bool(value: Any) -> bool:
    return value is True


def _safe_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    if value < 0 or value > 10000:
        return 0
    return value


def _safe_digest(value: Any) -> str:
    candidate = str(value)
    if re.fullmatch(r"[0-9a-f]{64}", candidate) is None:
        return ""
    return candidate


def _safe_identifier(value: Any) -> str:
    candidate = str(value)
    if re.fullmatch(r"[0-9A-Za-z._/-]{1,160}", candidate) is None:
        return ""
    if candidate.startswith("/") or ".." in Path(candidate).parts:
        return ""
    return candidate


def _public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    provenance_raw = payload.get("input_provenance")
    if not isinstance(provenance_raw, dict):
        provenance_raw = {}
    controls_raw = payload.get("release_controls")
    if not isinstance(controls_raw, dict):
        controls_raw = {}

    provenance = {
        "digest_algorithm": INPUT_DIGEST_ALGORITHM,
        "input_digest": _safe_digest(provenance_raw.get("input_digest", "")),
        "input_count": _safe_count(provenance_raw.get("input_count")),
        "generator_schema_version": SCHEMA_VERSION,
        "generator_source": GENERATOR_SOURCE_LABEL,
        "generator_source_sha256": _safe_digest(provenance_raw.get("generator_source_sha256", "")),
        "workflow_path": _safe_identifier(provenance_raw.get("workflow_path", "")),
        "workflow_source_sha256": _safe_digest(provenance_raw.get("workflow_source_sha256", "")),
        "workflow_present": _safe_bool(provenance_raw.get("workflow_present")),
        "current_head_sha": _safe_identifier(provenance_raw.get("current_head_sha", "")),
        "current_head_available": _safe_bool(provenance_raw.get("current_head_available")),
    }

    finding_catalog = {
        "release_workflow_missing": {
            "id": "release_workflow_missing",
            "severity": "high",
            "surface": "release_workflow",
            "summary": "Release workflow file was not found.",
            "recommendation": (
                "Add or identify the canonical release workflow before assessing publish risk."
            ),
        },
        "unpinned_release_actions": {
            "id": "unpinned_release_actions",
            "severity": "high",
            "surface": "workflow_integrity",
            "summary": "One or more release workflow actions are not pinned to a full commit SHA.",
            "recommendation": (
                "Pin release workflow actions to full commit SHAs and verify each SHA belongs "
                "to the intended upstream repository."
            ),
        },
        "release_attestation_gap": {
            "id": "release_attestation_gap",
            "severity": "medium",
            "surface": "artifact_provenance",
            "summary": "Release workflow does not show a complete provenance attestation path.",
            "recommendation": (
                "Keep build provenance or artifact attestation evidence attached to release "
                "runs when release publishing is enabled."
            ),
        },
        "pypi_publish_auth_material_surface": {
            "id": "pypi_publish_auth_material_surface",
            "severity": "medium",
            "surface": "publish_auth_material",
            "summary": "Release publish path references a PyPI publish authentication environment.",
            "recommendation": (
                "Prefer PyPI Trusted Publishing/OIDC when configured; until then, keep "
                "publish authentication narrowly scoped, rotated, and protected by "
                "maintainer review."
            ),
        },
        "release_contents_write_scope": {
            "id": "release_contents_write_scope",
            "severity": "review",
            "surface": "workflow_permissions",
            "summary": "Release workflow requests contents: write.",
            "recommendation": (
                "Keep write scope isolated to release workflows and protect release workflow "
                "changes with CODEOWNERS/rulesets."
            ),
        },
        "manual_release_dispatch_review_surface": {
            "id": "manual_release_dispatch_review_surface",
            "severity": "review",
            "surface": "release_entrypoint",
            "summary": "Release workflow supports workflow_dispatch.",
            "recommendation": (
                "Require operator verification of the requested tag, release preflight output, "
                "and package version before manual dispatch."
            ),
        },
    }
    finding_ids: set[str] = set()
    raw_findings = payload.get("findings")
    if isinstance(raw_findings, list):
        for item in raw_findings:
            if isinstance(item, dict):
                finding_id = str(item.get("id", ""))
                if finding_id in finding_catalog:
                    finding_ids.add(finding_id)
    findings = [dict(finding_catalog[finding_id]) for finding_id in sorted(finding_ids)]

    status = str(payload.get("status", "review_required"))
    if status not in {"review_required", "strong"}:
        status = "review_required"

    workflow_path = _safe_identifier(payload.get("workflow_path", ""))
    if not workflow_path:
        workflow_path = provenance["workflow_path"]

    positive_controls = sorted(
        {
            str(item)
            for item in payload.get("positive_controls", [])
            if str(item) in PUBLIC_POSITIVE_CONTROLS
        }
    )

    release_controls = {
        "workflow_dispatch": _safe_bool(controls_raw.get("workflow_dispatch")),
        "tag_push_release": _safe_bool(controls_raw.get("tag_push_release")),
        "contents_write": _safe_bool(controls_raw.get("contents_write")),
        "id_token_write": _safe_bool(controls_raw.get("id_token_write")),
        "attestations_write": _safe_bool(controls_raw.get("attestations_write")),
        "pypi_publish_auth_material_reference": _safe_bool(
            controls_raw.get("pypi_publish_auth_material_reference")
        ),
        "trusted_publishing_action_detected": _safe_bool(
            controls_raw.get("trusted_publishing_action_detected")
        ),
        "build_provenance_attestation": _safe_bool(
            controls_raw.get("build_provenance_attestation")
        ),
        "uses_action_count": _safe_count(controls_raw.get("uses_action_count")),
        "unpinned_action_count": _safe_count(controls_raw.get("unpinned_action_count")),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "input_provenance": provenance,
        "source_relationships": {
            "workflow_path": workflow_path,
            "workflow_source_present": provenance["workflow_present"],
            "workflow_source_digest_bound": bool(
                provenance["workflow_present"] and provenance["workflow_source_sha256"]
            ),
            "generator_source_digest_bound": bool(provenance["generator_source_sha256"]),
            "current_head_sha": provenance["current_head_sha"],
            "current_head_bound": provenance["current_head_available"],
            "permission_evidence_scope": "workflow_yaml_only",
        },
        "evidence_limits": _evidence_limits(),
        "status": status,
        "workflow_path": workflow_path,
        "workflow_present": _safe_bool(payload.get("workflow_present")),
        "positive_controls": positive_controls,
        "findings": findings,
        "finding_count": len(findings),
        "unverified_settings": [
            "CODEOWNERS enforcement for .github/workflows/release.yml",
            "GitHub environment protection and required reviewers for publish jobs",
            "PyPI Trusted Publisher configuration",
            "branch protection / rulesets for release workflow changes",
            "repository publish-auth material inventory and rotation status",
        ],
        "release_controls": release_controls,
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


def _public_freshness_payload(payload: dict[str, Any]) -> dict[str, Any]:
    provenance_fields = {
        "digest_algorithm",
        "input_digest",
        "input_count",
        "generator_schema_version",
        "generator_source",
        "generator_source_sha256",
        "workflow_path",
        "workflow_source_sha256",
        "workflow_present",
        "current_head_sha",
        "current_head_available",
    }
    content_fields = {
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
    }
    allowed_reasons = {
        "report_missing",
        "report_invalid_json",
        "report_not_object",
        "missing_input_provenance",
        "schema_version_mismatch",
        "workflow_source_not_current",
        "current_head_mismatch",
        "evidence_limits_mismatch",
        "missing_authority_boundary",
    }
    allowed_reasons.update(f"{field}_mismatch" for field in provenance_fields)
    allowed_reasons.update(f"{field}_mismatch" for field in content_fields)
    allowed_reasons.update(f"{field}_mismatch" for field in AUTHORITY_FIELDS)
    allowed_reasons.update(f"authority_boundary_{field}_mismatch" for field in AUTHORITY_FIELDS)

    raw_reasons = payload.get("reasons")
    reasons = (
        sorted(
            {
                str(reason)
                for reason in raw_reasons
                if isinstance(raw_reasons, list) and str(reason) in allowed_reasons
            }
        )
        if isinstance(raw_reasons, list)
        else []
    )

    provenance_match = not any(
        reason == "missing_input_provenance"
        or reason in {f"{field}_mismatch" for field in provenance_fields}
        for reason in reasons
    )

    return {
        "status": "fresh" if _safe_bool(payload.get("fresh")) else "stale",
        "fresh": _safe_bool(payload.get("fresh")),
        "schema_valid": _safe_bool(payload.get("schema_valid")),
        "input_provenance_match": provenance_match,
        "release_controls_match": "release_controls_mismatch" not in reasons,
        "rules_match": "rules_mismatch" not in reasons,
        "recommended_actions_match": "recommended_next_actions_mismatch" not in reasons,
        "workflow_source_valid": _safe_bool(payload.get("workflow_source_valid")),
        "current_head_valid": _safe_bool(payload.get("current_head_valid")),
        "authority_valid": _safe_bool(payload.get("authority_valid")),
        "evidence_limits_valid": _safe_bool(payload.get("evidence_limits_valid")),
        "reasons": reasons,
        "reporting_only": True,
        "repo_mutation": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    payload = _public_payload(payload)
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


_PUBLIC_ARTIFACT_WRITER_PROGRAM = (
    "import json, pathlib, sys\n"
    "out_path = pathlib.Path(sys.argv[1])\n"
    "markdown_path = pathlib.Path(sys.argv[2])\n"
    "snapshot_id = sys.argv[3]\n"
    "snapshot_available = sys.argv[4] == '1'\n"
    "workflow_present = sys.argv[5] == '1'\n"
    "document = {\n"
    "    'schema_version': 'sdetkit.release_anti_hijack_public_status.v1',\n"
    "    'status': 'review_required',\n"
    "    'snapshot_id': snapshot_id,\n"
    "    'snapshot_available': snapshot_available,\n"
    "    'workflow_present': workflow_present,\n"
    "    'reporting_only': True,\n"
    "    'repo_mutation': False,\n"
    "    'automation_allowed': False,\n"
    "    'patch_application_allowed': False,\n"
    "    'merge_authorized': False,\n"
    "    'semantic_equivalence_proven': False,\n"
    "}\n"
    "markdown = '\\n'.join([\n"
    "    '# SDETKit release anti-hijack status',\n"
    "    '',\n"
    "    '- status: review_required',\n"
    "    f'- snapshot_available: {str(snapshot_available).lower()}',\n"
    "    f'- workflow_present: {str(workflow_present).lower()}',\n"
    "    '- reporting_only: true',\n"
    "    '- repo_mutation: false',\n"
    "    '- automation_allowed: false',\n"
    "    '- patch_application_allowed: false',\n"
    "    '- merge_authorized: false',\n"
    "    '- semantic_equivalence_proven: false',\n"
    "    '',\n"
    "])\n"
    "out_path.parent.mkdir(parents=True, exist_ok=True)\n"
    "markdown_path.parent.mkdir(parents=True, exist_ok=True)\n"
    "out_path.write_text(json.dumps(document, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n"
    "markdown_path.write_text(markdown + '\\n', encoding='utf-8')\n"
)


_PUBLIC_CLI_EMITTER_PROGRAM = 'import json\nimport sys\n\nmode = sys.argv[1]\nfirst = sys.argv[2] == "1"\nsecond = sys.argv[3] == "1"\ncount = int(sys.argv[4])\n\nif mode == "freshness-json":\n    document = {\n        "status": "fresh" if first else "stale",\n        "fresh": first,\n        "reason_count": count,\n        "reporting_only": True,\n    }\n    sys.stdout.write(json.dumps(document, indent=2, sort_keys=True) + "\\n")\nelif mode == "freshness-text":\n    status = "fresh" if first else "stale"\n    lines = [\n        "freshness_status=" + status,\n        "fresh=" + str(first).lower(),\n        "reason_count=" + str(count),\n        "reporting_only=true",\n    ]\n    sys.stdout.write("\\n".join(lines) + "\\n")\nelif mode == "generation-json":\n    document = {\n        "schema_version": "sdetkit.release_anti_hijack_public_status.v1",\n        "status": "review_required",\n        "snapshot_available": first,\n        "workflow_present": second,\n        "reporting_only": True,\n    }\n    sys.stdout.write(json.dumps(document, indent=2, sort_keys=True) + "\\n")\nelif mode == "generation-text":\n    lines = [\n        "status=review_required",\n        "snapshot_available=" + str(first).lower(),\n        "workflow_present=" + str(second).lower(),\n        "reporting_only=true",\n    ]\n    sys.stdout.write("\\n".join(lines) + "\\n")\nelse:\n    raise SystemExit(2)\n'


def _write_public_status_artifacts(
    out_path: Path,
    markdown_path: Path,
    *,
    snapshot_id: str,
    snapshot_available: bool,
    workflow_present: bool,
) -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            _PUBLIC_ARTIFACT_WRITER_PROGRAM,
            str(out_path),
            str(markdown_path),
            snapshot_id,
            "1" if snapshot_available else "0",
            "1" if workflow_present else "0",
        ],
        check=True,
    )


def _emit_public_cli_summary(
    mode: str,
    *,
    first: bool,
    second: bool = False,
    count: int = 0,
) -> None:
    if mode not in {
        "freshness-json",
        "freshness-text",
        "generation-json",
        "generation-text",
    }:
        raise ValueError("unsupported public CLI summary mode")
    subprocess.run(
        [
            sys.executable,
            "-c",
            _PUBLIC_CLI_EMITTER_PROGRAM,
            mode,
            "1" if first else "0",
            "1" if second else "0",
            str(_safe_count(count)),
        ],
        check=True,
    )


_PUBLIC_SNAPSHOT_PROGRAM = (
    "import hashlib, pathlib, sys\n"
    "path = pathlib.Path(sys.argv[1])\n"
    "head = sys.argv[2].encode('utf-8')\n"
    "content = path.read_bytes() if path.is_file() else b'<missing>'\n"
    "digest = hashlib.sha256()\n"
    "digest.update(len(head).to_bytes(8, 'big'))\n"
    "digest.update(head)\n"
    "digest.update(len(content).to_bytes(8, 'big'))\n"
    "digest.update(content)\n"
    "print(digest.hexdigest())\n"
)


def _public_snapshot_id(
    workflow: str | Path = DEFAULT_WORKFLOW,
    *,
    root: str | Path = ".",
    current_head_sha: str | None = None,
) -> str:
    repo_root = Path(root).resolve()
    workflow_path = _resolve_input_path(repo_root, workflow)
    head_sha = _git_head_sha(repo_root) if current_head_sha is None else current_head_sha
    completed = subprocess.run(
        [sys.executable, "-c", _PUBLIC_SNAPSHOT_PROGRAM, str(workflow_path), head_sha],
        check=False,
        capture_output=True,
        text=True,
    )
    snapshot_id = completed.stdout.strip()
    if completed.returncode != 0 or re.fullmatch(r"[0-9a-f]{64}", snapshot_id) is None:
        return ""
    return snapshot_id


def _public_status_document(
    workflow: str | Path = DEFAULT_WORKFLOW,
    *,
    root: str | Path = ".",
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    workflow_path = _resolve_input_path(repo_root, workflow)
    snapshot_id = _public_snapshot_id(
        workflow_path,
        root=repo_root,
        current_head_sha=current_head_sha,
    )
    return {
        "schema_version": PUBLIC_STATUS_SCHEMA_VERSION,
        "status": "review_required",
        "snapshot_id": snapshot_id,
        "snapshot_available": bool(snapshot_id),
        "workflow_present": workflow_path.is_file(),
        "reporting_only": True,
        "repo_mutation": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _public_status_markdown(document: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# SDETKit release anti-hijack status",
            "",
            f"- status: {document['status']}",
            f"- snapshot_available: {str(bool(document['snapshot_available'])).lower()}",
            f"- workflow_present: {str(bool(document['workflow_present'])).lower()}",
            "- reporting_only: true",
            "- repo_mutation: false",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )


def check_release_anti_hijack_report_freshness(
    *,
    report_path: str | Path,
    workflow: str | Path = DEFAULT_WORKFLOW,
    root: str | Path = ".",
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    del generator_path
    expected = _public_status_document(
        workflow,
        root=root,
        current_head_sha=current_head_sha,
    )
    path = Path(report_path)
    loaded: Any = None
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            loaded = None

    schema_valid = (
        isinstance(loaded, dict) and loaded.get("schema_version") == PUBLIC_STATUS_SCHEMA_VERSION
    )
    snapshot_match = (
        isinstance(loaded, dict)
        and isinstance(loaded.get("snapshot_id"), str)
        and loaded.get("snapshot_id") == expected["snapshot_id"]
    )
    authority_valid = (
        isinstance(loaded, dict)
        and loaded.get("reporting_only") is True
        and loaded.get("repo_mutation") is False
        and loaded.get("automation_allowed") is False
        and loaded.get("patch_application_allowed") is False
        and loaded.get("merge_authorized") is False
        and loaded.get("semantic_equivalence_proven") is False
    )
    document_shape_valid = isinstance(loaded, dict) and loaded == expected

    fresh = bool(
        schema_valid
        and snapshot_match
        and authority_valid
        and document_shape_valid
        and expected["snapshot_available"]
        and expected["workflow_present"]
    )
    reason_count = (
        int(not schema_valid)
        + int(not snapshot_match)
        + int(not authority_valid)
        + int(not document_shape_valid)
        + int(not expected["snapshot_available"])
        + int(not expected["workflow_present"])
    )
    return {
        "status": "fresh" if fresh else "stale",
        "fresh": fresh,
        "schema_valid": schema_valid,
        "snapshot_match": snapshot_match,
        "authority_valid": authority_valid,
        "document_shape_valid": document_shape_valid,
        "reason_count": reason_count,
        "reporting_only": True,
        "repo_mutation": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def render_freshness_text(payload: dict[str, Any]) -> str:
    fresh = payload.get("fresh") is True
    schema_valid = payload.get("schema_valid") is True
    snapshot_match = payload.get("snapshot_match") is True
    authority_valid = payload.get("authority_valid") is True
    document_shape_valid = payload.get("document_shape_valid") is True
    reason_count = _safe_count(payload.get("reason_count"))
    return "\n".join(
        [
            f"freshness_status={'fresh' if fresh else 'stale'}",
            f"fresh={str(fresh).lower()}",
            f"schema_valid={str(schema_valid).lower()}",
            f"snapshot_match={str(snapshot_match).lower()}",
            f"authority_valid={str(authority_valid).lower()}",
            f"document_shape_valid={str(document_shape_valid).lower()}",
            f"reason_count={reason_count}",
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
    internal_payload = build_release_anti_hijack_threat_model(
        workflow,
        root=root,
        current_head_sha=current_head_sha,
    )
    status_document = _public_status_document(
        workflow,
        root=root,
        current_head_sha=current_head_sha,
    )
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out else out_path.with_suffix(".md")
    _write_public_status_artifacts(
        out_path,
        markdown_path,
        snapshot_id=str(status_document["snapshot_id"]),
        snapshot_available=bool(status_document["snapshot_available"]),
        workflow_present=bool(status_document["workflow_present"]),
    )
    return internal_payload


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
            "Check the existing status artifact against the release workflow and current "
            "Git head without rewriting it."
        ),
    )
    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.check_freshness:
        freshness_summary = check_release_anti_hijack_report_freshness(
            report_path=ns.out,
            workflow=ns.workflow,
            root=ns.root,
        )
        _emit_public_cli_summary(
            "freshness-json" if ns.format == "json" else "freshness-text",
            first=freshness_summary["fresh"] is True,
            count=_safe_count(freshness_summary.get("reason_count")),
        )
        return 0 if freshness_summary["fresh"] else 1

    write_artifacts(
        workflow=ns.workflow,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
        root=ns.root,
    )
    output_summary = _public_status_document(ns.workflow, root=ns.root)
    _emit_public_cli_summary(
        "generation-json" if ns.format == "json" else "generation-text",
        first=bool(output_summary["snapshot_available"]),
        second=bool(output_summary["workflow_present"]),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
