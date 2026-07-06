from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.doctor_report.v1"

AUTHORITY_BOUNDARY = {
    "reporting_only": True,
    "review_first": True,
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_claim": False,
}

ROADMAP_LANES = {
    "ascii": "operator_experience",
    "clean_tree": "green_main",
    "ci_workflows": "ci_reliability",
    "deps": "dependency_hygiene",
    "dev_tools": "developer_workflow",
    "pre_commit": "developer_workflow",
    "pyproject": "package_quality",
    "release_meta": "release_readiness",
    "repo_readiness": "architecture_health",
    "security_files": "security_posture",
    "stdlib_shadowing": "architecture_health",
    "upgrade_audit": "dependency_hygiene",
    "venv": "developer_workflow",
}

PROOF_COMMANDS = {
    "ascii": "python -m sdetkit doctor --ascii --format json",
    "clean_tree": "git status --short",
    "ci_workflows": "python -m sdetkit doctor --ci --format json",
    "deps": "python -m sdetkit doctor --deps --format json",
    "dev_tools": "python -m sdetkit doctor --dev --format json",
    "pre_commit": "python -m pre_commit run -a",
    "pyproject": "python -m sdetkit doctor --pyproject --format json",
    "release_meta": "python -m sdetkit doctor --release --format json",
    "repo_readiness": "python -m sdetkit doctor --repo --format json",
    "security_files": "python -m sdetkit doctor --ci --format json",
    "stdlib_shadowing": "python -m sdetkit doctor --dev --format json",
    "upgrade_audit": "python -m sdetkit doctor --upgrade-audit --format json",
    "venv": "python -m sdetkit doctor --dev --format json",
}


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: object) -> Sequence[object]:
    return (
        value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        else ()
    )


def _string(value: object, default: str = "") -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text or default


def _int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _severity_rank(severity: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(severity, 0)


def _status(
    payload: Mapping[str, Any], findings: Sequence[Mapping[str, object]]
) -> str:
    if findings:
        if any(_string(item.get("severity")) == "high" for item in findings):
            return "blocked"
        return "review_required"
    if _bool(payload.get("ok")):
        return "green"
    return "review_required"


def _confidence(
    payload: Mapping[str, Any], findings: Sequence[Mapping[str, object]]
) -> str:
    quality = _as_mapping(payload.get("quality"))
    evidence_count = _int(quality.get("evidence_count"))
    selected_checks = _int(quality.get("selected_checks"))
    if findings and evidence_count > 0:
        return "high"
    if selected_checks > 0 or findings:
        return "medium"
    return "low"


def _proof_command(check_id: str) -> str:
    return PROOF_COMMANDS.get(
        check_id, f"python -m sdetkit doctor --only {check_id} --format json"
    )


def _finding_from_next_action(item: Mapping[str, Any], index: int) -> dict[str, object]:
    check_id = _string(item.get("id"), "unknown")
    severity = _string(item.get("severity"), "medium")
    summary = _string(item.get("summary"), "Doctor check requires review")
    fixes = [_string(fix) for fix in _as_sequence(item.get("fix")) if _string(fix)]
    next_action = (
        fixes[0] if fixes else "Review the Doctor finding and run focused proof."
    )
    return {
        "id": f"doctor-finding-{index:02d}",
        "check_id": check_id,
        "title": summary,
        "severity": severity,
        "roadmap_lane": ROADMAP_LANES.get(check_id, "diagnosis_intelligence"),
        "root_cause": summary,
        "why_it_matters": _why_it_matters(check_id),
        "recommended_action": next_action,
        "proof_command": _proof_command(check_id),
        "review_first": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
    }


def _why_it_matters(check_id: str) -> str:
    return {
        "ascii": "Doctor output and source files should remain clear, readable, and operator-safe.",
        "clean_tree": "A dirty tree makes proof ambiguous because generated or local changes may affect the result.",
        "ci_workflows": "CI workflow gaps reduce confidence that the right checks run for the right surface.",
        "deps": "Dependency drift can break installs, tests, packaging, and downstream adoption.",
        "pre_commit": "Pre-commit is the fast local guardrail before CI and release proof.",
        "release_meta": "Release metadata must be consistent before package publication can be trusted.",
        "repo_readiness": "Repository readiness gaps make contributor and maintainer workflows harder to trust.",
        "security_files": "Security governance files make vulnerability reporting and review boundaries explicit.",
        "upgrade_audit": "Dependency upgrade decisions need evidence, impact classification, and proof commands.",
    }.get(
        check_id,
        "This signal affects repository reliability, diagnosis quality, or operator trust.",
    )


def _build_findings(payload: Mapping[str, Any]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for index, raw_item in enumerate(
        _as_sequence(payload.get("next_actions")), start=1
    ):
        item = _as_mapping(raw_item)
        if item:
            findings.append(_finding_from_next_action(item, index))
    return sorted(
        findings,
        key=lambda item: (
            -_severity_rank(_string(item.get("severity"))),
            _string(item.get("check_id")),
        ),
    )


def _summary(
    payload: Mapping[str, Any], findings: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    quality = _as_mapping(payload.get("quality"))
    return {
        "score": _int(payload.get("score")),
        "ok": _bool(payload.get("ok")),
        "selected_checks": _int(quality.get("selected_checks")),
        "actionable_checks": _int(quality.get("actionable_checks")),
        "passed_checks": _int(quality.get("passed_checks")),
        "failed_checks": _int(quality.get("failed_checks")),
        "skipped_checks": _int(quality.get("skipped_checks")),
        "finding_count": len(findings),
    }


def _primary_finding(findings: Sequence[Mapping[str, object]]) -> dict[str, object]:
    if findings:
        top = findings[0]
        return {
            "title": _string(top.get("title"), "Doctor finding requires review"),
            "severity": _string(top.get("severity"), "medium"),
            "check_id": _string(top.get("check_id"), "unknown"),
            "roadmap_lane": _string(top.get("roadmap_lane"), "diagnosis_intelligence"),
            "next_action": _string(
                top.get("recommended_action"), "Review Doctor output."
            ),
            "proof_command": _string(
                top.get("proof_command"), "python -m sdetkit doctor --format json"
            ),
        }
    return {
        "title": "No blocking Doctor findings detected",
        "severity": "none",
        "check_id": "none",
        "roadmap_lane": "green_main",
        "next_action": "Keep baseline proof current and continue with the next roadmap-aligned slice.",
        "proof_command": "python -m sdetkit doctor --all --format json",
    }


def _roadmap_alignment(findings: Sequence[Mapping[str, object]]) -> dict[str, object]:
    lanes = sorted(
        {
            _string(item.get("roadmap_lane"))
            for item in findings
            if item.get("roadmap_lane")
        }
    )
    if not lanes:
        lanes = ["green_main"]
    return {
        "lanes": lanes,
        "next_best_lane": lanes[0],
        "strategy": "Resolve blocking findings first, then continue diagnosis-intelligence work in small PRs.",
    }


def build_doctor_report_contract(payload: Mapping[str, Any]) -> dict[str, object]:
    """Build the professional Doctor report contract from a standard Doctor payload."""

    findings = _build_findings(payload)
    status = _status(payload, findings)
    contract = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "confidence": _confidence(payload, findings),
        "summary": _summary(payload, findings),
        "primary_finding": _primary_finding(findings),
        "findings": findings,
        "safety_decision": {
            **AUTHORITY_BOUNDARY,
            "reason": "Doctor report is advisory and review-first until proof and verifier boundaries are implemented.",
        },
        "roadmap_alignment": _roadmap_alignment(findings),
        "proof_commands": sorted(
            {
                _string(item.get("proof_command"))
                for item in findings
                if item.get("proof_command")
            }
        )
        or ["python -m sdetkit doctor --all --format json"],
    }
    return contract


def render_doctor_report_markdown(contract: Mapping[str, object]) -> str:
    """Render a clean human-readable Doctor report contract."""

    summary = _as_mapping(contract.get("summary"))
    primary = _as_mapping(contract.get("primary_finding"))
    safety = _as_mapping(contract.get("safety_decision"))
    roadmap = _as_mapping(contract.get("roadmap_alignment"))
    findings = [_as_mapping(item) for item in _as_sequence(contract.get("findings"))]
    proof_commands = [
        _string(item)
        for item in _as_sequence(contract.get("proof_commands"))
        if _string(item)
    ]

    lines = [
        "# SDETKit Doctor Report",
        "",
        "## Status",
        f"- status: `{_string(contract.get('status'), 'unknown')}`",
        f"- confidence: `{_string(contract.get('confidence'), 'low')}`",
        f"- score: `{_int(summary.get('score'))}%`",
        f"- findings: `{_int(summary.get('finding_count'))}`",
        "",
        "## Primary Finding",
        f"- title: `{_string(primary.get('title'), 'No finding')}`",
        f"- severity: `{_string(primary.get('severity'), 'none')}`",
        f"- roadmap_lane: `{_string(primary.get('roadmap_lane'), 'green_main')}`",
        f"- next_action: `{_string(primary.get('next_action'), 'Review Doctor output.')}`",
        f"- proof_command: `{_string(primary.get('proof_command'), 'python -m sdetkit doctor --format json')}`",
        "",
        "## Findings",
    ]
    if findings:
        for item in findings:
            lines.extend(
                [
                    f"### {_string(item.get('check_id'), 'unknown')}",
                    f"- severity: `{_string(item.get('severity'), 'medium')}`",
                    f"- root_cause: `{_string(item.get('root_cause'), 'review required')}`",
                    f"- why_it_matters: `{_string(item.get('why_it_matters'), 'operator trust')}`",
                    f"- recommended_action: `{_string(item.get('recommended_action'), 'review finding')}`",
                    f"- proof_command: `{_string(item.get('proof_command'), 'python -m sdetkit doctor --format json')}`",
                    "",
                ]
            )
    else:
        lines.extend(["- none", ""])

    lines.extend(
        [
            "## Safety Decision",
            f"- review_first: `{str(_bool(safety.get('review_first'))).lower()}`",
            f"- automation_allowed: `{str(_bool(safety.get('automation_allowed'))).lower()}`",
            f"- patch_application_allowed: `{str(_bool(safety.get('patch_application_allowed'))).lower()}`",
            f"- merge_authorized: `{str(_bool(safety.get('merge_authorized'))).lower()}`",
            f"- semantic_equivalence_claim: `{str(_bool(safety.get('semantic_equivalence_claim'))).lower()}`",
            f"- reason: `{_string(safety.get('reason'), 'review-first advisory report')}`",
            "",
            "## Roadmap Alignment",
            "- lanes: "
            + ", ".join(
                f"`{_string(lane)}`" for lane in _as_sequence(roadmap.get("lanes"))
            ),
            f"- next_best_lane: `{_string(roadmap.get('next_best_lane'), 'green_main')}`",
            f"- strategy: `{_string(roadmap.get('strategy'), 'continue in small PRs')}`",
            "",
            "## Proof Commands",
        ]
    )
    lines.extend(f"- `{command}`" for command in proof_commands)
    lines.append("")
    return "\n".join(lines)


def write_doctor_report_contract(contract: Mapping[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
