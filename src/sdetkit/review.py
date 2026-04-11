from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

from . import doctor, inspect_project
from .evidence_workspace import load_workspace_manifest, record_workspace_run
from .inspect_compare import run_compare
from .inspect_data import run_inspect
from .judgment import build_judgment, load_latest_previous_payload

SCHEMA_VERSION = "sdetkit.review.v1"
EXIT_OK = 0
EXIT_FINDINGS = 2


def _safe_slug(value: str) -> str:
    out: list[str] = []
    for ch in value.lower():
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "review"


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"review: expected JSON object at {path}")
    return loaded


def _detect_mode(target: Path) -> dict[str, bool]:
    is_dir = target.is_dir()
    repo_like = is_dir and ((target / ".git").exists() or (target / "pyproject.toml").exists())
    policy_project = is_dir and (target / "inspect-project.json").exists()
    data_like = False
    if target.is_file() and target.suffix.lower() in {".csv", ".json"}:
        data_like = True
    elif is_dir:
        data_files = [
            p
            for p in target.rglob("*")
            if p.is_file() and p.suffix.lower() in {".csv", ".json"} and ".sdetkit" not in p.parts
        ]
        data_like = bool(data_files)
    workspace_like = is_dir and ((target / ".sdetkit" / "workspace" / "manifest.json").exists())
    return {
        "repo_like": repo_like,
        "policy_project": policy_project,
        "data_like": data_like,
        "workspace_like": workspace_like,
    }


def _run_doctor(target: Path, out_dir: Path, workspace_root: Path, no_workspace: bool) -> tuple[int, dict[str, Any], Path]:
    doctor_json = out_dir / "doctor.json"
    args = [
        "--json",
        "--repo",
        "--ci",
        "--deps",
        "--clean-tree",
        "--workspace-root",
        str(workspace_root),
        "--out",
        str(doctor_json),
    ]
    if no_workspace:
        args.append("--no-workspace")
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    # doctor operates on cwd repo state.
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        try:
            rc = doctor.main(args)
        except SystemExit as exc:
            rc = int(exc.code)
    payload = _load_json(doctor_json)
    return int(rc), payload, doctor_json


def _review_scope_for_target(target: Path) -> str:
    return _safe_slug(target.resolve().as_posix())


def _summarize_changed(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(previous, dict):
        return [{"kind": "baseline", "message": "No previous review run found for this scope."}]
    changes: list[dict[str, Any]] = []
    prev_actions = previous.get("prioritized_actions", [])
    cur_actions = current.get("prioritized_actions", [])
    prev_now = len([a for a in prev_actions if isinstance(a, dict) and a.get("tier") == "now"])
    cur_now = len([a for a in cur_actions if isinstance(a, dict) and a.get("tier") == "now"])
    if prev_now != cur_now:
        changes.append(
            {
                "kind": "action_pressure",
                "message": f"immediate_actions changed {prev_now} -> {cur_now}",
            }
        )
    prev_status = str(previous.get("status", ""))
    cur_status = str(current.get("status", ""))
    if prev_status != cur_status:
        changes.append({"kind": "status", "message": f"status changed {prev_status} -> {cur_status}"})
    prev_sev = str(previous.get("severity", ""))
    cur_sev = str(current.get("severity", ""))
    if prev_sev != cur_sev:
        changes.append({"kind": "severity", "message": f"severity changed {prev_sev} -> {cur_sev}"})
    return changes or [{"kind": "stable", "message": "No material review-level changes detected."}]


def run_review(
    *,
    target: Path,
    out_dir: Path,
    workspace_root: Path,
    no_workspace: bool = False,
) -> tuple[int, dict[str, Any], Path, Path]:
    target = target.resolve()
    if not target.exists():
        raise ValueError(f"review: path does not exist: {target}")

    detection = _detect_mode(target)
    out_dir.mkdir(parents=True, exist_ok=True)

    source_workflows: list[dict[str, Any]] = []
    supporting: list[dict[str, Any]] = []
    conflicting: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    healthy_controls: list[str] = []
    prioritized_actions: list[dict[str, Any]] = []
    artifact_index: dict[str, str] = {}

    # deterministic order: doctor -> inspect -> inspect-compare -> inspect-project -> history
    if detection["repo_like"]:
        doctor_out = out_dir / "doctor"
        doctor_out.mkdir(parents=True, exist_ok=True)
        prev_cwd = Path.cwd()
        try:
            if target.is_dir():
                import os

                os.chdir(target)
            doctor_rc, doctor_payload, doctor_json = _run_doctor(
                target,
                doctor_out,
                workspace_root,
                no_workspace,
            )
        finally:
            import os

            os.chdir(prev_cwd)
        artifact_index["doctor_json"] = doctor_json.as_posix()
        source_workflows.append({"workflow": "doctor", "status": "ok" if doctor_rc == 0 else "findings"})
        if doctor_rc == 0:
            healthy_controls.append("doctor checks passed for repo hygiene and release controls")
        else:
            findings.append(
                {
                    "id": "review:doctor",
                    "kind": "doctor",
                    "severity": "high",
                    "priority": 70,
                    "why_it_matters": "doctor reported repo-level release risks",
                    "next_action": "Address failing doctor checks before promotion decisions.",
                    "message": "doctor reported findings",
                }
            )
            prioritized_actions.append(
                {
                    "tier": "now",
                    "priority": 70,
                    "action": "Fix doctor failures in repo governance and hygiene checks.",
                }
            )
        supporting.append({"kind": "doctor_ok", "value": bool(doctor_payload.get("ok", False))})

    inspect_payload: dict[str, Any] | None = None
    if detection["data_like"] and not detection["policy_project"]:
        inspect_out = out_dir / "inspect"
        inspect_rc, inspect_payload, inspect_json_path, inspect_txt_path = run_inspect(
            input_path=target,
            out_dir=inspect_out,
            workspace_root=workspace_root,
            record_workspace=not no_workspace,
            workspace_scope=_review_scope_for_target(target),
        )
        artifact_index["inspect_json"] = inspect_json_path.as_posix()
        artifact_index["inspect_txt"] = inspect_txt_path.as_posix()
        source_workflows.append({"workflow": "inspect", "status": "ok" if inspect_rc == 0 else "findings"})
        supporting.append({"kind": "inspect_files", "value": inspect_payload.get("summary", {}).get("files_analyzed", 0)})
        if inspect_rc == 0:
            healthy_controls.append("inspect evidence diagnostics are stable")
        else:
            findings.append(
                {
                    "id": "review:inspect",
                    "kind": "inspect",
                    "severity": "high",
                    "priority": 65,
                    "why_it_matters": "inspect surfaced suspicious evidence or rule failures",
                    "next_action": "Investigate inspect anomalies and resolve suspicious signals.",
                    "message": "inspect reported findings",
                }
            )
            prioritized_actions.append(
                {
                    "tier": "now",
                    "priority": 65,
                    "action": "Resolve inspect evidence anomalies and rerun review.",
                }
            )

    if detection["policy_project"]:
        project_out = out_dir / "inspect-project"
        rc = inspect_project.main(
            [
                str(target),
                "--workspace-root",
                str(workspace_root),
                "--out-dir",
                str(project_out),
                "--format",
                "json",
                *( ["--no-workspace"] if no_workspace else []),
            ]
        )
        payload = _load_json(project_out / "inspect-project.json")
        artifact_index["inspect_project_json"] = (project_out / "inspect-project.json").as_posix()
        artifact_index["inspect_project_txt"] = (project_out / "inspect-project.txt").as_posix()
        source_workflows.append({"workflow": "inspect-project", "status": "ok" if rc == 0 else "findings"})
        supporting.append({"kind": "inspect_project_scopes", "value": payload.get("summary", {}).get("scopes", 0)})
        if rc != 0:
            findings.append(
                {
                    "id": "review:inspect-project",
                    "kind": "inspect-project",
                    "severity": "high",
                    "priority": 60,
                    "why_it_matters": "inspect-project policy pack found high-signal scope risks",
                    "next_action": "Remediate failing scopes in inspect-project outputs.",
                    "message": "inspect-project reported findings",
                }
            )

    if inspect_payload and not no_workspace:
        scope = _review_scope_for_target(target)
        previous_inspect, _ = load_latest_previous_payload(
            workspace_root=workspace_root,
            workflow="inspect",
            scope=scope,
        )
        if isinstance(previous_inspect, dict):
            compare_out = out_dir / "inspect-compare"
            compare_rc, compare_payload, compare_json, compare_txt = run_compare(
                left_payload=previous_inspect,
                right_payload=inspect_payload,
                left_label="workspace:previous",
                right_label="workspace:current",
                out_dir=compare_out,
                out_scope=scope,
                workspace_root=workspace_root,
                record_workspace=not no_workspace,
            )
            artifact_index["inspect_compare_json"] = compare_json.as_posix()
            artifact_index["inspect_compare_txt"] = compare_txt.as_posix()
            source_workflows.append(
                {"workflow": "inspect-compare", "status": "ok" if compare_rc == 0 else "findings"}
            )
            drift_score = int(compare_payload.get("summary", {}).get("drift_score", 0))
            supporting.append({"kind": "drift_score", "value": drift_score})
            if compare_rc != 0:
                findings.append(
                    {
                        "id": "review:inspect-compare",
                        "kind": "inspect-compare",
                        "severity": "medium",
                        "priority": min(55, 20 + drift_score * 4),
                        "why_it_matters": "recent evidence drift changed baseline behavior",
                        "next_action": "Review drift files and approve intended changes.",
                        "message": "inspect-compare detected drift",
                    }
                )

    if detection["workspace_like"]:
        manifest = load_workspace_manifest(target / ".sdetkit" / "workspace")
        supporting.append({"kind": "workspace_runs", "value": len(manifest.get("runs", []))})
        source_workflows.append({"workflow": "workspace-history", "status": "ok"})

    # contradictions as first-class product output
    has_doctor_failure = any(f.get("kind") == "doctor" for f in findings)
    has_inspect_failure = any(f.get("kind") == "inspect" for f in findings)
    if has_doctor_failure and not has_inspect_failure:
        conflicting.append(
            {
                "id": "review:conflict:repo-vs-data",
                "kind": "cross_surface_disagreement",
                "message": "Repo controls fail while local evidence diagnostics appear healthy.",
            }
        )
    if has_inspect_failure and not has_doctor_failure and detection["repo_like"]:
        conflicting.append(
            {
                "id": "review:conflict:data-vs-repo",
                "kind": "cross_surface_disagreement",
                "message": "Repo controls pass while evidence diagnostics show anomalies.",
            }
        )

    completeness = min(1.0, max(0.2, len(source_workflows) / 5.0))
    stability = 0.7 if conflicting else 0.85
    workflow_ok = len(findings) == 0
    blocking = any(int(item.get("priority", 0)) >= 60 for item in findings) or bool(conflicting)

    review_judgment = build_judgment(
        workflow="review",
        findings=findings,
        supporting_evidence=supporting,
        conflicting_evidence=conflicting,
        completeness=completeness,
        stability=stability,
        previous_summary=None,
        workflow_ok=workflow_ok,
        blocking=blocking,
    )

    prioritized_actions.extend(review_judgment.get("recommendations", []))
    review_scope = _review_scope_for_target(target)
    previous_review = None
    previous_hash = None
    if not no_workspace:
        previous_review, previous_hash = load_latest_previous_payload(
            workspace_root=workspace_root,
            workflow="review",
            scope=review_scope,
        )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit",
        "workflow": "review",
        "path": target.as_posix(),
        "status": review_judgment.get("status"),
        "severity": review_judgment.get("severity"),
        "confidence": review_judgment.get("confidence", {}),
        "review_status": "PASS" if workflow_ok else "ATTENTION",
        "top_matters": review_judgment.get("top_judgment", {}).get("what_matters_most", []),
        "supporting_evidence": supporting,
        "conflicting_evidence": conflicting,
        "healthy_controls": healthy_controls,
        "changed_since_previous": [],
        "prioritized_actions": prioritized_actions[:8],
        "source_workflows_run": source_workflows,
        "artifact_index": artifact_index,
        "judgment": review_judgment,
        "history": {
            "workspace_root": workspace_root.as_posix(),
            "has_previous_review": bool(previous_review),
            "previous_review_run_hash": previous_hash,
        },
        "detection": detection,
    }
    payload["changed_since_previous"] = _summarize_changed(previous_review, payload)

    json_path = out_dir / "review.json"
    txt_path = out_dir / "review.txt"
    json_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    txt_path.write_text(_render_text(payload), encoding="utf-8")

    if not no_workspace:
        workspace_entry = record_workspace_run(
            workspace_root=workspace_root,
            workflow="review",
            scope=review_scope,
            payload=payload,
            artifacts={"review_json": json_path.as_posix(), "review_text": txt_path.as_posix()},
            recommendations=[str(item.get("action", "")) for item in payload.get("prioritized_actions", []) if isinstance(item, dict)],
        )
        payload["workspace"] = workspace_entry
        json_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    rc = EXIT_OK if payload["status"] == "pass" else EXIT_FINDINGS
    return rc, payload, json_path, txt_path


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"SDETKit review: {payload['review_status']}",
        f"path: {payload['path']}",
        f"status: {payload['status']} severity: {payload['severity']}",
        f"confidence: {payload.get('confidence', {}).get('score')}",
        "top_matters:",
    ]
    for item in payload.get("top_matters", [])[:5]:
        if not isinstance(item, dict):
            continue
        lines.append(f"- [{item.get('priority', 0)}] {item.get('kind')}: {item.get('message')}")
    lines.append("what_to_do_now:")
    for action in payload.get("prioritized_actions", []):
        if not isinstance(action, dict):
            continue
        if str(action.get("tier")) == "now":
            lines.append(f"- {action.get('action')}")
    lines.append("what_to_do_next:")
    for action in payload.get("prioritized_actions", []):
        if not isinstance(action, dict):
            continue
        if str(action.get("tier")) == "next":
            lines.append(f"- {action.get('action')}")
    lines.append("what_to_monitor:")
    for action in payload.get("prioritized_actions", []):
        if not isinstance(action, dict):
            continue
        if str(action.get("tier")) == "monitor":
            lines.append(f"- {action.get('action')}")
    if payload.get("conflicting_evidence"):
        lines.append(f"conflicts: {len(payload['conflicting_evidence'])}")
    lines.append("")
    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit review",
        description="Front-door SDETKit review workflow that orchestrates doctor/inspect/compare/project/history.",
    )
    p.add_argument("path", help="Repo/data/project/workspace path to review")
    p.add_argument("--workspace-root", default=".sdetkit/workspace", help="Shared workspace root")
    p.add_argument("--out-dir", default=None, help="Output directory (default: .sdetkit/review/<path-slug>)")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--no-workspace", action="store_true", help="Disable workspace history recording")
    return p


def main(argv: list[str] | None = None) -> int:
    ns = _build_arg_parser().parse_args(argv)
    target = Path(ns.path)
    out_dir = Path(ns.out_dir) if ns.out_dir else Path(".sdetkit") / "review" / _safe_slug(target.resolve().name)
    try:
        rc, payload, _, _ = run_review(
            target=target,
            out_dir=out_dir,
            workspace_root=Path(ns.workspace_root),
            no_workspace=ns.no_workspace,
        )
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return EXIT_FINDINGS

    output = json.dumps(payload, sort_keys=True) if ns.format == "json" else _render_text(payload)
    sys.stdout.write(output + ("\n" if not output.endswith("\n") else ""))
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
