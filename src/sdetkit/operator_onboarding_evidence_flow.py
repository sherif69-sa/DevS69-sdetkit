"""Operator onboarding evidence flow.

This module creates a deterministic, reporting-only source map for the operator
onboarding path. It does not run remediation, apply patches, authorize merge,
or claim semantic equivalence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]

SCHEMA_VERSION = "sdetkit.operator_onboarding_evidence_flow.v1"

_AUTHORITY_BOUNDARY: JsonObject = {
    "boundary_mode": "reporting_only",
    "automation_allowed": False,
    "patch_application_allowed": False,
    "merge_authorized": False,
    "security_dismissal_allowed": False,
    "semantic_equivalence_claim": False,
    "semantic_equivalence_proven": False,
}

_REQUIRED_SURFACES = [
    "operator-onramp",
    "operator-onramp-dry-run",
    "operator-onramp-verify",
    "operator-onboarding-wizard",
    "onboarding-next",
    "operator evidence loop",
    "operator brief",
    "operator evidence review guide",
]

_FLOW_STEPS: list[JsonObject] = [
    {
        "id": "dry_run_onramp",
        "title": "Dry-run the operator onramp",
        "command": "make operator-onramp-dry-run",
        "artifact": "",
        "human_review_required": True,
    },
    {
        "id": "run_first_proof",
        "title": "Collect first-proof evidence",
        "command": "make first-proof-local",
        "artifact": "build/first-proof/first-proof-summary.json",
        "human_review_required": True,
    },
    {
        "id": "generate_onboarding_next",
        "title": "Generate onboarding next actions",
        "command": "make onboarding-next",
        "artifact": "build/onboarding-next.json",
        "human_review_required": True,
    },
    {
        "id": "run_onboarding_wizard",
        "title": "Run operator onboarding wizard",
        "command": "make operator-onboarding-wizard",
        "artifact": ".sdetkit/out/operator-onboarding-summary.json",
        "human_review_required": True,
    },
    {
        "id": "build_operator_brief",
        "title": "Build operator brief",
        "command": "python -m sdetkit.operator_brief --format md --out build/sdetkit/operator-brief.md",
        "artifact": "build/sdetkit/operator-brief.md",
        "human_review_required": True,
    },
    {
        "id": "build_operator_evidence_loop",
        "title": "Build operator evidence loop",
        "command": "python -m sdetkit.operator_evidence_loop --format markdown --out-dir build/sdetkit/operator-loop",
        "artifact": "build/sdetkit/operator-loop/operator-loop.json",
        "human_review_required": True,
    },
    {
        "id": "verify_onramp",
        "title": "Verify operator onramp evidence",
        "command": "make operator-onramp-verify",
        "artifact": "build/first-proof/followup-ready.json",
        "human_review_required": True,
    },
]


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _has(text: str, needle: str) -> bool:
    return needle.lower() in text.lower()


def _surface(
    *,
    surface_id: str,
    title: str,
    source: str,
    detected: bool,
    command: str = "",
) -> JsonObject:
    return {
        "id": surface_id,
        "title": title,
        "source": source,
        "detected": detected,
        "status": "present" if detected else "missing",
        "command": command,
        "reporting_only": True,
        "human_review_required": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
    }


def _artifact_observation(repo_root: Path, artifact: str) -> JsonObject:
    if not artifact:
        return {
            "path": "",
            "exists": False,
            "required_for_flow_definition": False,
            "note": "Command-only step; no local artifact is required to define the flow.",
        }
    path = repo_root / artifact
    return {
        "path": artifact,
        "exists": path.exists(),
        "required_for_flow_definition": False,
        "note": "Runtime artifact may be absent until the operator executes the step.",
    }


def build_operator_onboarding_evidence_flow(repo_root: str | Path = ".") -> JsonObject:
    root = Path(repo_root)
    makefile = _read_text(root / "Makefile")
    operator_loop = _read_text(root / "src/sdetkit/operator_evidence_loop.py")
    operator_brief = _read_text(root / "src/sdetkit/operator_brief.py")
    wizard = _read_text(root / "scripts/operator_onboarding_wizard.py")
    onboarding_next = _read_text(root / "scripts/operator_onboarding_next.py")
    guide = _read_text(root / "docs/operator-evidence-review-guide.md")
    onboarding_docs = _read_text(root / "docs/operator-onboarding-7-day.md")

    surfaces = [
        _surface(
            surface_id="operator_onramp",
            title="Operator onramp Make target",
            source="Makefile",
            detected=_has(makefile, "operator-onramp:"),
            command="make operator-onramp",
        ),
        _surface(
            surface_id="operator_onramp_dry_run",
            title="Operator onramp dry-run target",
            source="Makefile",
            detected=_has(makefile, "operator-onramp-dry-run:"),
            command="make operator-onramp-dry-run",
        ),
        _surface(
            surface_id="operator_onramp_verify",
            title="Operator onramp verification target",
            source="Makefile",
            detected=_has(makefile, "operator-onramp-verify:"),
            command="make operator-onramp-verify",
        ),
        _surface(
            surface_id="operator_onboarding_wizard",
            title="Operator onboarding wizard",
            source="scripts/operator_onboarding_wizard.py and Makefile",
            detected=_has(wizard, "operator-onboarding")
            and _has(makefile, "operator-onboarding-wizard"),
            command="make operator-onboarding-wizard",
        ),
        _surface(
            surface_id="onboarding_next",
            title="Onboarding next action plan",
            source="scripts/operator_onboarding_next.py and Makefile",
            detected=_has(onboarding_next, "onboarding-next")
            and _has(makefile, "onboarding-next:"),
            command="make onboarding-next",
        ),
        _surface(
            surface_id="operator_evidence_loop",
            title="Operator evidence loop",
            source="src/sdetkit/operator_evidence_loop.py",
            detected=_has(operator_loop, "sdetkit.operator.evidence_loop.v1"),
            command="python -m sdetkit.operator_evidence_loop",
        ),
        _surface(
            surface_id="operator_brief",
            title="Operator brief",
            source="src/sdetkit/operator_brief.py",
            detected=_has(operator_brief, "sdetkit.operator_brief.v1"),
            command="python -m sdetkit.operator_brief",
        ),
        _surface(
            surface_id="operator_review_docs",
            title="Operator evidence review guide",
            source="docs/operator-evidence-review-guide.md and docs/operator-onboarding-7-day.md",
            detected=_has(guide, "Operator evidence review guide")
            and _has(onboarding_docs, "operator"),
            command="open docs/operator-evidence-review-guide.md",
        ),
    ]

    present_count = sum(1 for surface in surfaces if surface["detected"] is True)
    missing = [surface for surface in surfaces if surface["detected"] is not True]
    status = "ready_for_operator_review" if not missing else "review_required"

    steps = []
    for index, step in enumerate(_FLOW_STEPS, start=1):
        copied = dict(step)
        copied["order"] = index
        copied["reporting_only"] = True
        copied["automation_allowed"] = False
        copied["patch_application_allowed"] = False
        copied["merge_authorized"] = False
        copied["artifact_observation"] = _artifact_observation(root, str(step.get("artifact", "")))
        steps.append(copied)

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit.operator_onboarding_evidence_flow",
        "status": status,
        "reporting_only": True,
        "review_first": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_claim": False,
        "authority_boundary": dict(_AUTHORITY_BOUNDARY),
        "summary": {
            "required_surface_count": len(surfaces),
            "present_surface_count": present_count,
            "missing_surface_count": len(missing),
            "flow_step_count": len(steps),
            "status": status,
            "next_allowed_action": "human_operator_review",
        },
        "required_surfaces": list(_REQUIRED_SURFACES),
        "surfaces": surfaces,
        "flow_steps": steps,
        "blocked_actions": [
            "automatic_remediation",
            "automatic_patch_application",
            "automatic_merge",
            "automatic_security_dismissal",
            "semantic_equivalence_claim",
        ],
        "next_allowed_action": "human_operator_review",
    }


def render_operator_onboarding_evidence_markdown(payload: JsonObject) -> str:
    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    lines = [
        "# Operator onboarding evidence flow",
        "",
        f"- schema_version: `{payload.get('schema_version', 'unknown')}`",
        f"- status: `{payload.get('status', 'unknown')}`",
        f"- reporting_only: `{str(bool(payload.get('reporting_only', True))).lower()}`",
        f"- review_first: `{str(bool(payload.get('review_first', True))).lower()}`",
        f"- automation_allowed: `{str(bool(payload.get('automation_allowed', False))).lower()}`",
        f"- patch_application_allowed: `{str(bool(payload.get('patch_application_allowed', False))).lower()}`",
        f"- merge_authorized: `{str(bool(payload.get('merge_authorized', False))).lower()}`",
        f"- semantic_equivalence_claim: `{str(bool(payload.get('semantic_equivalence_claim', False))).lower()}`",
        f"- next_allowed_action: `{payload.get('next_allowed_action', 'human_operator_review')}`",
        "",
        "## Summary",
        "",
        f"- required_surface_count: `{summary.get('required_surface_count', 0)}`",
        f"- present_surface_count: `{summary.get('present_surface_count', 0)}`",
        f"- missing_surface_count: `{summary.get('missing_surface_count', 0)}`",
        f"- flow_step_count: `{summary.get('flow_step_count', 0)}`",
        "",
        "## Flow steps",
        "",
    ]

    for step in payload.get("flow_steps", []):
        if not isinstance(step, dict):
            continue
        lines.extend(
            [
                f"### {step.get('order', '?')}. {step.get('title', step.get('id', 'unknown'))}",
                f"- id: `{step.get('id', 'unknown')}`",
                f"- command: `{step.get('command', '')}`",
                f"- artifact: `{step.get('artifact', '')}`",
                "- human_review_required: `true`",
                "- automation_allowed: `false`",
                "- patch_application_allowed: `false`",
                "- merge_authorized: `false`",
                "",
            ]
        )

    lines.extend(["## Surfaces", ""])
    for surface in payload.get("surfaces", []):
        if not isinstance(surface, dict):
            continue
        lines.append(
            f"- `{surface.get('id', 'unknown')}`: `{surface.get('status', 'unknown')}` "
            f"from `{surface.get('source', 'unknown')}`"
        )

    lines.extend(["", "## Authority boundary", ""])
    boundary = payload.get("authority_boundary", {})
    if isinstance(boundary, dict):
        for key, value in boundary.items():
            rendered = str(value).lower() if isinstance(value, bool) else value
            lines.append(f"- {key}: `{rendered}`")

    lines.extend(
        [
            "",
            "_Reporting-only. This flow does not authorize remediation, patch application, merge, security dismissal, or semantic-equivalence claims._",
        ]
    )
    return "\n".join(lines)


def write_operator_onboarding_evidence_flow(
    repo_root: str | Path = ".",
    out_json: str | Path = "build/sdetkit/operator-onboarding-evidence-flow/flow.json",
    out_md: str | Path = "build/sdetkit/operator-onboarding-evidence-flow/flow.md",
) -> JsonObject:
    payload = build_operator_onboarding_evidence_flow(repo_root)
    json_path = Path(out_json)
    md_path = Path(out_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(
        render_operator_onboarding_evidence_markdown(payload) + "\n", encoding="utf-8"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.operator_onboarding_evidence_flow")
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--out-json", default="build/sdetkit/operator-onboarding-evidence-flow/flow.json"
    )
    parser.add_argument(
        "--out-md", default="build/sdetkit/operator-onboarding-evidence-flow/flow.md"
    )
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args(argv)

    payload = write_operator_onboarding_evidence_flow(
        repo_root=args.root,
        out_json=args.out_json,
        out_md=args.out_md,
    )
    if args.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_operator_onboarding_evidence_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
