from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
from typing import Any

from sdetkit import (
    evidence_graph,
    mission_control,
    pr_quality_action_report,
    pr_quality_evidence_narrative,
    safe_fix_operator_rollup,
)

SCHEMA_VERSION = "sdetkit.operator.evidence_loop.v1"
REPORTING_PROJECTIONS_SCHEMA_VERSION = ".".join(
    ("sdetkit", "operator", "evidence", "loop", "reporting", "projections", "v1")
)
REPORTING_PROJECTIONS = "_".join(("reporting", "projections"))
TRAJECTORY_HISTORY_PROJECTION = "_".join(("trajectory", "history", "projection"))
PATCH_SCORE_PROJECTION = "_".join(("patch", "score", "projection"))
PROTECTED_VERIFIER_PROJECTION = "_".join(("protected", "verifier", "projection"))
CURRENT_PR_DECISION_INPUT = "_".join(("current", "pr", "decision", "input"))
PRODUCER_EXECUTION_CHANGED = "_".join(("producer", "execution", "changed"))
DEFAULT_OUTPUT_DIR = Path("build/sdetkit/operator-loop")

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    rendered = str(value).strip()
    return rendered or default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _string_list(value: Any, *, limit: int = 20) -> list[str]:
    values = [_string(item) for item in _as_list(value) if _string(item)]
    return values[: max(limit, 0)]


def _artifact_key(*parts: str) -> str:
    return "_".join(parts)


def _build_or_reuse_evidence_graph(
    *,
    out_dir: Path,
    sentinel_control_room: Path | None,
    evidence_graph_path: Path | None,
    failure_bundle: Path | None,
    pr_quality_action_report_path: Path | None,
) -> tuple[Path, JsonObject]:
    if evidence_graph_path is not None and evidence_graph_path.exists():
        return evidence_graph_path, {
            "graph_path": evidence_graph_path.as_posix(),
            "reused": True,
        }

    graph = evidence_graph.build_evidence_graph(
        sentinel_control_room=sentinel_control_room,
        failure_bundle=failure_bundle,
        pr_quality_action_report=pr_quality_action_report_path,
    )
    manifest = evidence_graph.write_evidence_graph(
        graph,
        output_dir=out_dir / "evidence-graph",
    )
    return Path(str(manifest["graph_path"])), dict(manifest)


def _run_mission_control(
    *,
    repo: Path,
    out_dir: Path,
    graph_path: Path,
    failure_bundle: Path | None,
) -> Path:
    mission_out = out_dir / "mission-control"
    argv = [
        "run",
        "--repo",
        str(repo),
        "--out-dir",
        str(mission_out),
        "--evidence-graph",
        str(graph_path),
        "--no-ledger",
    ]
    if failure_bundle is not None:
        argv.extend(["--failure-bundle", str(failure_bundle)])

    # Mission Control is a nested producer here. Keep its human-oriented stdout
    # out of this command's machine-readable stdout contract.
    with contextlib.redirect_stdout(io.StringIO()):
        rc = mission_control.main(argv)
    if rc != 0:
        raise RuntimeError(f"mission control failed with exit code {rc}")

    return mission_out / "mission-control.json"


def _default_action_report(evidence_narrative: JsonObject) -> JsonObject:
    quality = _as_dict(evidence_narrative.get("quality"))
    status = "green" if quality.get("ok") is True else "failed"
    return {
        "status": status,
        "primary_blocker": {},
        "automation": {
            "attempted": False,
            "allowed": False,
            "reason": "operator evidence loop is advisory-only",
        },
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }


def _default_check_intelligence() -> JsonObject:
    return {
        "checks_seen": 0,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": False, "unresolved_findings": 0},
    }


def _read_optional_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return _as_dict(payload)


def _write_safe_fix_outcome_rollup(
    *,
    out_dir: Path,
    check_intelligence: Path | None,
) -> tuple[JsonObject, JsonObject]:
    rollup_dir = out_dir / "safe-fix-outcome-rollup"
    payload = _read_optional_json(check_intelligence)
    rollup = safe_fix_operator_rollup.write_rollup(payload, rollup_dir)
    return rollup, {
        _artifact_key("safe", "fix", "outcome", "rollup", "json"): (
            rollup_dir / "safe-fix-outcome-rollup.json"
        ).as_posix(),
        _artifact_key("safe", "fix", "outcome", "rollup", "markdown"): (
            rollup_dir / "safe-fix-outcome-rollup.md"
        ).as_posix(),
    }


def _projection_boundary() -> JsonObject:
    return {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }


def _not_collected_projection(source: str) -> JsonObject:
    return {
        "collection_status": "not_collected",
        "source": source,
        "source_schema": "not_collected",
        "reporting_only": True,
        CURRENT_PR_DECISION_INPUT: False,
        PRODUCER_EXECUTION_CHANGED: False,
        "decision_boundary": _projection_boundary(),
    }


def _trajectory_history_projection(
    payload: JsonObject,
) -> JsonObject:
    if not payload:
        return _not_collected_projection("trajectory_history_report")

    recent = [
        {
            "diagnostic_id": _string(_as_dict(item).get("diagnostic_id")),
            "action": _string(_as_dict(item).get("action")),
            "failure_class": _string(_as_dict(item).get("failure_class")),
            "risk_surface": _string(_as_dict(item).get("risk_surface")),
            "review_first": _bool(_as_dict(item).get("review_first")),
            "auto_fix_allowed": _bool(_as_dict(item).get("auto_fix_allowed")),
            "final_result": _string(_as_dict(item).get("final_result")),
        }
        for item in _as_list(payload.get("recent_decisions"))[:5]
        if _as_dict(item)
    ]

    return {
        "collection_status": "collected",
        "source": "trajectory_history_report",
        "source_schema": (_string(payload.get("schema_version")) or "unknown"),
        "record_count": _int(payload.get("record_count")),
        "review_first_count": _int(payload.get("review_first_count")),
        "auto_fix_allowed_count": _int(payload.get("auto_fix_allowed_count")),
        "by_final_result": _as_dict(payload.get("by_final_result")),
        "by_risk_surface": _as_dict(payload.get("by_risk_surface")),
        "by_failure_class": _as_dict(payload.get("by_failure_class")),
        "by_action": _as_dict(payload.get("by_action")),
        "recent_decisions": recent,
        "reporting_only": True,
        CURRENT_PR_DECISION_INPUT: False,
        PRODUCER_EXECUTION_CHANGED: False,
        "decision_boundary": _projection_boundary(),
    }


def _patch_score_projection(
    payload: JsonObject,
) -> JsonObject:
    if not payload:
        return _not_collected_projection("patch_scorer")

    decision = _as_dict(payload.get("decision"))
    flags = [_as_dict(item) for item in _as_list(payload.get("risk_flags")) if _as_dict(item)]

    return {
        "collection_status": "collected",
        "source": "patch_scorer",
        "source_schema": (_string(payload.get("schema_version")) or "unknown"),
        "patch_id": _string(payload.get("patch_id")),
        "diagnosis_id": _string(payload.get("diagnosis_id")),
        "failure_surface": _string(payload.get("failure_surface")),
        "classification": _string(payload.get("classification")),
        "risk_level": _string(payload.get("risk_level")),
        "strategy": _string(payload.get("strategy")),
        "score": _int(payload.get("score")),
        "minimum_score": _int(payload.get("minimum_score")),
        "changed_files": _string_list(payload.get("changed_files")),
        "risk_flag_count": len(flags),
        "blocking_risk_flag_count": sum(1 for flag in flags if _bool(flag.get("blocking"))),
        "risk_flag_codes": sorted(
            {_string(flag.get("code")) for flag in flags if _string(flag.get("code"))}
        ),
        "source_decision_status": _string(decision.get("status")),
        "source_candidate_for_protected_verification": (
            _bool(decision.get("candidate_for_protected_verification"))
        ),
        "source_automation_allowed": _bool(decision.get("automation_allowed")),
        "reporting_only": True,
        CURRENT_PR_DECISION_INPUT: False,
        PRODUCER_EXECUTION_CHANGED: False,
        "decision_boundary": _projection_boundary(),
    }


def _protected_verifier_projection(
    payload: JsonObject,
) -> JsonObject:
    if not payload:
        return _not_collected_projection("protected_verifier")

    decision = _as_dict(payload.get("decision"))
    findings = [_as_dict(item) for item in _as_list(payload.get("findings")) if _as_dict(item)]
    risk_flags = [_as_dict(item) for item in _as_list(payload.get("risk_flags")) if _as_dict(item)]

    return {
        "collection_status": "collected",
        "source": "protected_verifier",
        "source_schema": (_string(payload.get("schema_version")) or "unknown"),
        "patch_id": _string(payload.get("patch_id")),
        "diagnosis_id": _string(payload.get("diagnosis_id")),
        "patch_score": _int(payload.get("patch_score")),
        "source_decision_status": _string(decision.get("status")),
        "source_review_first": _bool(decision.get("review_first")),
        "source_structural_verification_passed": (
            _bool(decision.get("structural_verification_passed"))
            or _bool(decision.get("protected_verification_passed"))
        ),
        "source_semantic_equivalence_proven": (_bool(decision.get("semantic_equivalence_proven"))),
        "source_automation_allowed": _bool(decision.get("automation_allowed")),
        "source_merge_authorized": _bool(decision.get("merge_authorized")),
        "finding_count": len(findings),
        "risk_flag_count": len(risk_flags),
        "blocking_finding_count": sum(1 for finding in findings if _bool(finding.get("blocking"))),
        "reporting_only": True,
        CURRENT_PR_DECISION_INPUT: False,
        PRODUCER_EXECUTION_CHANGED: False,
        "decision_boundary": _projection_boundary(),
    }


def _reporting_projections(
    *,
    trajectory_history: JsonObject,
    patch_score: JsonObject,
    protected_verifier_decision: JsonObject,
) -> JsonObject:
    return {
        "schema_version": (REPORTING_PROJECTIONS_SCHEMA_VERSION),
        TRAJECTORY_HISTORY_PROJECTION: (_trajectory_history_projection(trajectory_history)),
        PATCH_SCORE_PROJECTION: (_patch_score_projection(patch_score)),
        PROTECTED_VERIFIER_PROJECTION: (
            _protected_verifier_projection(protected_verifier_decision)
        ),
        "reporting_only": True,
        CURRENT_PR_DECISION_INPUT: False,
        PRODUCER_EXECUTION_CHANGED: False,
        "decision_boundary": _projection_boundary(),
    }


def _classification(
    *,
    evidence_narrative: JsonObject,
    mission_bundle: JsonObject,
) -> str:
    quality = _as_dict(evidence_narrative.get("quality"))
    if quality.get("ok") is not True:
        return "failed"

    patch_plan = _as_dict(mission_bundle.get("patch_plan"))
    if patch_plan.get("enabled") and patch_plan.get("requires_human_review"):
        return "review_required"

    graph = _as_dict(mission_bundle.get("evidence_graph"))
    if _int(graph.get("review_first_count")) > 0:
        return "review_required"

    return "green"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _artifact_exists(artifacts: JsonObject, *parts: str) -> bool:
    value = artifacts.get(_artifact_key(*parts))
    return bool(value) and Path(str(value)).exists()


def _verify_operator_loop_payload(payload: JsonObject) -> JsonObject:
    artifacts = _as_dict(payload.get("artifacts"))
    required_artifacts = [
        ("evidence", "graph", "json"),
        ("mission", "control", "json"),
        ("pr", "quality", "narrative", "json"),
        ("pr", "quality", "narrative", "markdown"),
        ("pr", "quality", "comment", "markdown"),
        ("operator", "loop", "json"),
        ("operator", "loop", "markdown"),
    ]

    missing = [
        _artifact_key(*parts)
        for parts in required_artifacts
        if not _artifact_exists(artifacts, *parts)
    ]

    boundary = _as_dict(payload.get("automation_boundary"))
    advisory_ok = payload.get("advisory_only") is True and all(
        boundary.get(key) is False
        for key in [
            "executes_patch_commands",
            "mutates_source",
            "dismisses_security_findings",
            "pushes_or_merges",
        ]
    )

    reporting = _as_dict(payload.get(REPORTING_PROJECTIONS))
    reporting_boundary = _as_dict(reporting.get("decision_boundary"))
    reporting_projection_ok = (
        reporting.get("schema_version") == REPORTING_PROJECTIONS_SCHEMA_VERSION
        and reporting.get("reporting_only") is True
        and reporting.get(CURRENT_PR_DECISION_INPUT) is False
        and reporting.get(PRODUCER_EXECUTION_CHANGED) is False
        and all(
            reporting_boundary.get(key) is False
            for key in [
                "automation_allowed",
                "patch_application_allowed",
                "merge_authorized",
                "semantic_equivalence_proven",
                "automatic_security_fix_allowed",
                "automatic_dismissal_allowed",
            ]
        )
    )

    comment_key = _artifact_key("pr", "quality", "comment", "markdown")
    comment_path = Path(str(artifacts.get(comment_key, "")))
    comment_ok = comment_path.exists() and "SDETKit Review Result" in comment_path.read_text(
        encoding="utf-8"
    )

    mission_key = _artifact_key("mission", "control", "json")
    mission_ok = bool(_read_json(Path(str(artifacts.get(mission_key, "")))))

    patch_plan = _as_dict(payload.get("patch_plan"))
    patch_plan_expected = payload.get("classification") == "review_required"
    patch_plan_ok = bool(patch_plan) if patch_plan_expected else True

    checks = {
        "required_artifacts": not missing,
        "advisory_boundary": advisory_ok,
        "reporting_projection_boundary": (reporting_projection_ok),
        "comment": comment_ok,
        "mission": mission_ok,
        "patch_plan": patch_plan_ok,
    }

    return {
        "ok": all(checks.values()),
        "missing_artifacts": missing,
        "checks": checks,
    }


def _safe_fix_rollup_lines(rollup: JsonObject) -> list[str]:
    if not rollup:
        return ["- not collected"]

    recommendation = _as_dict(rollup.get("recommendation"))
    lines = [
        f"- Status: `{rollup.get('status', 'unknown')}`",
        f"- Outcomes: `{_int(rollup.get('outcome_count'))}`",
        f"- Attempted: `{_int(rollup.get('attempted_count'))}`",
        f"- Committed: `{_int(rollup.get('committed_count'))}`",
        f"- Pushed: `{_int(rollup.get('pushed_count'))}`",
        f"- Safe candidates: `{_int(rollup.get('safe_candidate_count'))}`",
        f"- Review-first blockers: `{_int(rollup.get('review_first_blocker_count'))}`",
        f"- Recommendation: `{recommendation.get('action', 'unknown')}`",
    ]

    files = [_as_dict(item) for item in _as_list(rollup.get("recurring_files"))]
    if files:
        lines.append("- Recurring files:")
        for item in files[:5]:
            lines.append(f"  - `{item.get('path', '')}` seen `{_int(item.get('count'))}` time(s)")

    reasons = [_as_dict(item) for item in _as_list(rollup.get("refusal_reasons"))]
    if reasons:
        lines.append("- Refusal reasons:")
        for item in reasons[:5]:
            lines.append(
                f"  - `{item.get('reason', 'unknown')}` seen `{_int(item.get('count'))}` time(s)"
            )

    return lines


def _render_markdown(payload: JsonObject) -> str:
    artifacts = _as_dict(payload.get("artifacts"))
    mission_control_summary = _as_dict(payload.get("mission_control"))
    patch_plan = _as_dict(payload.get("patch_plan"))
    safe_fix_rollup = _as_dict(payload.get("safe_fix_outcome_rollup"))

    reporting = _as_dict(payload.get(REPORTING_PROJECTIONS))
    reporting_boundary = _as_dict(reporting.get("decision_boundary"))
    trajectory_projection = _as_dict(reporting.get(TRAJECTORY_HISTORY_PROJECTION))
    patch_score_projection = _as_dict(reporting.get(PATCH_SCORE_PROJECTION))
    verifier_projection = _as_dict(reporting.get(PROTECTED_VERIFIER_PROJECTION))

    lines = [
        "# Operator evidence loop",
        "",
        f"- Classification: `{payload.get('classification', 'unknown')}`",
        f"- Quality outcome: `{payload.get('quality_outcome', 'unknown')}`",
        f"- Mission decision: `{mission_control_summary.get('decision', 'unknown')}`",
        f"- Mission risk band: `{mission_control_summary.get('risk_band', 'unknown')}`",
        "",
        "## Review-first patch plan",
        "",
    ]

    if patch_plan:
        lines.extend(
            [
                f"- Enabled: `{str(bool(patch_plan.get('enabled', False))).lower()}`",
                f"- Status: `{_string(patch_plan.get('status'), 'unknown')}`",
                f"- Source kind: `{_string(patch_plan.get('source_kind'), 'unknown')}`",
                f"- Source code: `{_string(patch_plan.get('source_code'), 'UNKNOWN')}`",
                f"- Safe to auto-fix: `{str(bool(patch_plan.get('safe_to_auto_fix', False))).lower()}`",
                f"- Dry run only: `{str(bool(patch_plan.get('dry_run_only', True))).lower()}`",
                f"- Requires human review: `{str(bool(patch_plan.get('requires_human_review', True))).lower()}`",
            ]
        )
    else:
        lines.append("- none")

    verification = _as_dict(payload.get("verification"))
    if verification:
        checks = _as_dict(verification.get("checks"))
        lines.extend(
            [
                "",
                "## Verification",
                "",
                f"- OK: `{str(bool(verification.get('ok', False))).lower()}`",
                f"- Missing artifacts: `{len(_as_list(verification.get('missing_artifacts')))}`",
            ]
        )
        for key in sorted(checks):
            lines.append(f"- {key}: `{str(bool(checks[key])).lower()}`")

    lines.extend(
        [
            "",
            "## Safe-fix outcome rollup",
            "",
            *_safe_fix_rollup_lines(safe_fix_rollup),
        ]
    )

    lines.extend(
        [
            "",
            "## Read-only reporting projections",
            "",
            (f"- Schema: `{_string(reporting.get('schema_version'), 'unknown')}`"),
            (f"- Reporting only: `{str(_bool(reporting.get('reporting_only'))).lower()}`"),
            (
                "- Current PR decision input: "
                f"`{str(_bool(reporting.get(CURRENT_PR_DECISION_INPUT))).lower()}`"
            ),
            (
                "- Producer execution changed: "
                f"`{str(_bool(reporting.get(PRODUCER_EXECUTION_CHANGED))).lower()}`"
            ),
            (
                "- Patch application allowed: "
                f"`{str(_bool(reporting_boundary.get('patch_application_allowed'))).lower()}`"
            ),
            (
                "- Automation allowed: "
                f"`{str(_bool(reporting_boundary.get('automation_allowed'))).lower()}`"
            ),
            (
                "- Merge authorized: "
                f"`{str(_bool(reporting_boundary.get('merge_authorized'))).lower()}`"
            ),
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(reporting_boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            "",
            "### Trajectory history",
            "",
            (
                "- Collection status: "
                f"`{_string(trajectory_projection.get('collection_status'), 'unknown')}`"
            ),
            (f"- Records: `{_int(trajectory_projection.get('record_count'))}`"),
            (
                "- Review-first decisions: "
                f"`{_int(trajectory_projection.get('review_first_count'))}`"
            ),
            (
                "- Auto-fix-allowed decisions: "
                f"`{_int(trajectory_projection.get('auto_fix_allowed_count'))}`"
            ),
            "",
            "### PatchScorer",
            "",
            (
                "- Collection status: "
                f"`{_string(patch_score_projection.get('collection_status'), 'unknown')}`"
            ),
            (
                "- Decision status: "
                f"`{_string(patch_score_projection.get('source_decision_status'), 'unknown')}`"
            ),
            (f"- Score: `{_int(patch_score_projection.get('score'))}`"),
            (
                "- Blocking risk flags: "
                f"`{_int(patch_score_projection.get('blocking_risk_flag_count'))}`"
            ),
            "",
            "### ProtectedVerifier",
            "",
            (
                "- Collection status: "
                f"`{_string(verifier_projection.get('collection_status'), 'unknown')}`"
            ),
            (
                "- Decision status: "
                f"`{_string(verifier_projection.get('source_decision_status'), 'unknown')}`"
            ),
            (
                "- Structural verification passed: "
                f"`{str(_bool(verifier_projection.get('source_structural_verification_passed'))).lower()}`"
            ),
            (f"- Blocking findings: `{_int(verifier_projection.get('blocking_finding_count'))}`"),
        ]
    )

    lines.extend(["", "## Artifacts", ""])
    for key in sorted(artifacts):
        lines.append(f"- {key}: `{artifacts[key]}`")

    return "\n".join(lines).rstrip() + "\n"


def build_operator_evidence_loop(
    *,
    repo: Path,
    out_dir: Path = DEFAULT_OUTPUT_DIR,
    quality_log: Path | None = None,
    quality_outcome: str = "unknown",
    sentinel_control_room: Path | None = None,
    evidence_graph_path: Path | None = None,
    failure_bundle: Path | None = None,
    changed_files: Path | None = None,
    action_report: Path | None = None,
    check_intelligence: Path | None = None,
    trajectory_history: Path | None = None,
    patch_score: Path | None = None,
    protected_verifier_decision: Path | None = None,
) -> JsonObject:
    out_dir.mkdir(parents=True, exist_ok=True)

    graph_path, graph_manifest = _build_or_reuse_evidence_graph(
        out_dir=out_dir,
        sentinel_control_room=sentinel_control_room,
        evidence_graph_path=evidence_graph_path,
        failure_bundle=failure_bundle,
        pr_quality_action_report_path=action_report,
    )

    mission_bundle_path = _run_mission_control(
        repo=repo,
        out_dir=out_dir,
        graph_path=graph_path,
        failure_bundle=failure_bundle,
    )
    mission_bundle = _read_json(mission_bundle_path)

    evidence_narrative = pr_quality_evidence_narrative.build_narrative(
        quality_log=quality_log,
        quality_outcome=quality_outcome,
        sentinel_control_room=sentinel_control_room,
        evidence_graph=graph_path,
        failure_bundle=failure_bundle,
        mission_control=mission_bundle_path,
        changed_files=changed_files,
    )

    narrative_json = out_dir / "pr-quality-narrative.json"
    narrative_markdown = out_dir / "pr-quality-narrative.md"
    _write_json(narrative_json, evidence_narrative)
    _write_text(narrative_markdown, _string(evidence_narrative.get("markdown")))

    action_payload = _read_json(action_report) or _default_action_report(evidence_narrative)
    check_payload = _read_json(check_intelligence) or _default_check_intelligence()
    trajectory_payload = _read_optional_json(trajectory_history)
    patch_score_payload = _read_optional_json(patch_score)
    protected_verifier_payload = _read_optional_json(protected_verifier_decision)
    reporting_projections = _reporting_projections(
        trajectory_history=trajectory_payload,
        patch_score=patch_score_payload,
        protected_verifier_decision=(protected_verifier_payload),
    )
    comment_body = pr_quality_action_report.render_comment_body(
        action_report=action_payload,
        check_intelligence=check_payload,
        evidence_narrative=evidence_narrative,
    )
    comment_path = out_dir / "pr-quality-comment.md"
    _write_text(comment_path, comment_body)

    artifacts: JsonObject = {
        _artifact_key("evidence", "graph", "json"): graph_path.as_posix(),
        _artifact_key("mission", "control", "json"): mission_bundle_path.as_posix(),
        _artifact_key("pr", "quality", "narrative", "json"): narrative_json.as_posix(),
        _artifact_key("pr", "quality", "narrative", "markdown"): narrative_markdown.as_posix(),
        _artifact_key("pr", "quality", "comment", "markdown"): comment_path.as_posix(),
    }

    for source_path, artifact_parts in (
        (
            trajectory_history,
            ("trajectory", "history", "json"),
        ),
        (
            patch_score,
            ("patch", "score", "json"),
        ),
        (
            protected_verifier_decision,
            ("protected", "verifier", "json"),
        ),
    ):
        if source_path is not None and source_path.exists():
            artifacts[_artifact_key(*artifact_parts)] = source_path.as_posix()

    evidence_graph_markdown = graph_path.parent / "evidence-graph.md"
    if evidence_graph_markdown.exists():
        artifacts[_artifact_key("evidence", "graph", "markdown")] = (
            evidence_graph_markdown.as_posix()
        )

    mission_markdown = mission_bundle_path.parent / "mission-control.md"
    if mission_markdown.exists():
        artifacts[_artifact_key("mission", "control", "markdown")] = mission_markdown.as_posix()

    safe_fix_rollup, safe_fix_rollup_artifacts = _write_safe_fix_outcome_rollup(
        out_dir=out_dir,
        check_intelligence=check_intelligence,
    )

    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "classification": _classification(
            evidence_narrative=evidence_narrative,
            mission_bundle=mission_bundle,
        ),
        "repo": repo.as_posix(),
        "quality_outcome": quality_outcome,
        "evidence_graph": graph_manifest,
        "mission_control": {
            "decision": mission_bundle.get("decision", "unknown"),
            "risk_band": mission_bundle.get("risk_band", "unknown"),
            "evidence_graph": mission_bundle.get("evidence_graph", {}),
        },
        "patch_plan": mission_bundle.get("patch_plan", {}),
        REPORTING_PROJECTIONS: reporting_projections,
        "pr_quality": {
            "primary_signal": evidence_narrative.get("primary_signal", {}),
            "quality": evidence_narrative.get("quality", {}),
        },
        "artifacts": artifacts,
        "advisory_only": True,
        "automation_boundary": {
            "executes_patch_commands": False,
            "mutates_source": False,
            "dismisses_security_findings": False,
            "pushes_or_merges": False,
        },
    }
    payload["safe_fix_outcome_rollup"] = safe_fix_rollup
    _as_dict(payload.setdefault("artifacts", {})).update(safe_fix_rollup_artifacts)

    loop_json = out_dir / "operator-loop.json"
    loop_markdown = out_dir / "operator-loop.md"
    payload["artifacts"][_artifact_key("operator", "loop", "json")] = loop_json.as_posix()
    payload["artifacts"][_artifact_key("operator", "loop", "markdown")] = loop_markdown.as_posix()

    _write_json(loop_json, payload)
    _write_text(loop_markdown, _render_markdown(payload))

    payload["verification"] = _verify_operator_loop_payload(payload)
    _write_json(loop_json, payload)
    _write_text(loop_markdown, _render_markdown(payload))
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.operator_evidence_loop",
        description="Build a read-only operator evidence loop from existing SDETKit artifacts.",
    )
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--quality-log", type=Path, default=None)
    parser.add_argument("--quality-outcome", default="unknown")
    parser.add_argument("--sentinel-control-room", type=Path, default=None)
    parser.add_argument("--evidence-graph", type=Path, default=None)
    parser.add_argument("--failure-bundle", type=Path, default=None)
    parser.add_argument("--changed-files", type=Path, default=None)
    parser.add_argument("--action-report", type=Path, default=None)
    parser.add_argument("--check-intelligence", type=Path, default=None)
    parser.add_argument("--trajectory-history", type=Path, default=None)
    parser.add_argument("--patch-score", type=Path, default=None)
    parser.add_argument("--protected-verifier", type=Path, default=None)
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Return a non-zero exit code when the generated operator loop is incomplete.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_operator_evidence_loop(
        repo=args.repo,
        out_dir=args.out_dir,
        quality_log=args.quality_log,
        quality_outcome=str(args.quality_outcome),
        sentinel_control_room=args.sentinel_control_room,
        evidence_graph_path=args.evidence_graph,
        failure_bundle=args.failure_bundle,
        changed_files=args.changed_files,
        action_report=args.action_report,
        check_intelligence=args.check_intelligence,
        trajectory_history=args.trajectory_history,
        patch_score=args.patch_score,
        protected_verifier_decision=(args.protected_verifier),
    )

    if args.format == "markdown":
        print(_render_markdown(payload), end="")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    if args.verify and not bool(_as_dict(payload.get("verification")).get("ok", False)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
