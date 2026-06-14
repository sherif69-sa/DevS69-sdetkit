"""Release-readiness evidence packaging.

This module builds a deterministic, reporting-only release evidence packet.
It inspects local release/package surfaces and summarizes what a human reviewer
should verify before a release. It never authorizes publishing, merging, patch
automation, or semantic-equivalence claims.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]

SCHEMA_VERSION = "sdetkit.release_readiness_evidence_package.v1"

_AUTHORITY_BOUNDARY: JsonObject = {
    "boundary_mode": "reporting_only",
    "release_authorization": False,
    "publish_authorization": False,
    "merge_authorization": False,
    "patch_automation": False,
    "security_dismissal": False,
    "semantic_equivalence_claim": False,
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
    "python -m pytest -q tests/test_release_preflight.py tests/test_release_readiness.py tests/test_release_room_plan.py -o addopts=",
    "make proof-after-format",
]


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


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


def build_release_readiness_evidence_package(repo_root: str | Path = ".") -> JsonObject:
    root = Path(repo_root)
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
            detected=_has(makefile, "force-reinstall", "dist/*.whl", "sdetkit --help")
            and _has(release_workflow, "force-reinstall", "dist/*.whl", "sdetkit --help"),
            command="python -m pip install --force-reinstall dist/*.whl && sdetkit --help",
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
            detected=_has(release_workflow, "upload-artifact", "release-diagnostics"),
            command="upload build/release-preflight.json as release diagnostics",
        ),
        _evidence_item(
            evidence_id="post_publish_or_rollback_plan",
            title="Post-publish or rollback verification plan",
            source="Makefile/release-verify-plan and docs/release-readiness-evidence-handoff.md",
            detected=_has(makefile, "release_verify_post_publish.py")
            and (_has(release_handoff, "blocked") or _has(artifact_reference, "release")),
            command="make release-verify-plan",
        ),
    ]

    present_count = sum(1 for item in evidence_items if item["detected"] is True)
    missing = [item for item in evidence_items if item["detected"] is not True]
    status = "ready_for_human_release_review" if not missing else "review_required"

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit.release_readiness_evidence_package",
        "status": status,
        "reporting_only": True,
        "review_first": True,
        "safe_to_publish": False,
        "release_authorized": False,
        "authority_boundary": dict(_AUTHORITY_BOUNDARY),
        "summary": {
            "required_evidence_count": len(evidence_items),
            "present_evidence_count": present_count,
            "missing_evidence_count": len(missing),
            "status": status,
            "next_allowed_action": "human_release_review",
        },
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


def render_release_readiness_evidence_markdown(payload: JsonObject) -> str:
    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    lines = [
        "# Release-readiness evidence package",
        "",
        f"- schema_version: `{payload.get('schema_version', 'unknown')}`",
        f"- status: `{payload.get('status', 'unknown')}`",
        f"- reporting_only: `{str(bool(payload.get('reporting_only', True))).lower()}`",
        f"- review_first: `{str(bool(payload.get('review_first', True))).lower()}`",
        f"- safe_to_publish: `{str(bool(payload.get('safe_to_publish', False))).lower()}`",
        f"- release_authorized: `{str(bool(payload.get('release_authorized', False))).lower()}`",
        f"- next_allowed_action: `{payload.get('next_allowed_action', 'human_release_review')}`",
        "",
        "## Summary",
        "",
        f"- required_evidence_count: `{summary.get('required_evidence_count', 0)}`",
        f"- present_evidence_count: `{summary.get('present_evidence_count', 0)}`",
        f"- missing_evidence_count: `{summary.get('missing_evidence_count', 0)}`",
        "",
        "## Evidence items",
        "",
    ]

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

    lines.extend(["", "## Authority boundary", ""])
    boundary = payload.get("authority_boundary", {})
    if isinstance(boundary, dict):
        for key, value in boundary.items():
            rendered = str(value).lower() if isinstance(value, bool) else value
            lines.append(f"- {key}: `{rendered}`")

    lines.extend(
        [
            "",
            "_Reporting-only. This package does not authorize release, publish, merge, patch automation, security dismissal, or semantic-equivalence claims._",
        ]
    )
    return "\n".join(lines)


def write_release_readiness_evidence_package(
    repo_root: str | Path = ".",
    out_json: str | Path = "build/sdetkit/release-readiness-evidence/package.json",
    out_md: str | Path = "build/sdetkit/release-readiness-evidence/package.md",
) -> JsonObject:
    payload = build_release_readiness_evidence_package(repo_root)
    json_path = Path(out_json)
    md_path = Path(out_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_release_readiness_evidence_markdown(payload) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit.release-readiness-evidence-package")
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--out-json", default="build/sdetkit/release-readiness-evidence/package.json"
    )
    parser.add_argument("--out-md", default="build/sdetkit/release-readiness-evidence/package.md")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args(argv)

    payload = write_release_readiness_evidence_package(
        repo_root=args.root,
        out_json=args.out_json,
        out_md=args.out_md,
    )

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_release_readiness_evidence_markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
