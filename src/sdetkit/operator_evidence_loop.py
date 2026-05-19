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
