from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import cast

from ..bools import coerce_bool
from .artifacts import (
    ArtifactPaths,
    artifact_paths_for,
    render_record_artifacts,
    render_report_artifacts,
)
from .base import CheckStatus, PlannerHint
from .planner import CheckPlanner
from .registry import default_registry
from .results import CheckRecord
from .runner import CheckRunner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.checks")
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name in ("plan", "run", "render-ledger"):
        command = sub.add_parser(name)
        if name != "render-ledger":
            command.add_argument(
                "--profile", choices=["quick", "standard", "strict", "adaptive"], required=True
            )
        else:
            command.add_argument(
                "--profile", choices=["quick", "standard", "strict", "adaptive"], required=True
            )
            command.add_argument("--ledger", required=True)
            command.add_argument("--requested-profile", default=None)
            command.add_argument("--profile-notes", default="")
            command.add_argument("--metadata-json", default=None)
        command.add_argument("--repo-root", default=".")
        command.add_argument("--out-dir", default=".sdetkit/out")
        if name != "render-ledger":
            command.add_argument("--changed-path", action="append", default=None)
            command.add_argument("--reason", action="append", default=None)
            command.add_argument("--no-targeting", action="store_true")
        command.add_argument("--format", choices=["json", "text"], default="json")
        if name in {"run", "render-ledger"}:
            command.add_argument("--json-output", default=None)
            command.add_argument("--markdown-output", default=None)
            command.add_argument("--fix-plan-output", default=None)
            command.add_argument("--risk-summary-output", default=None)
            command.add_argument("--evidence-output", default=None)
            command.add_argument("--run-report-output", default=None)
            command.add_argument("--emit-legacy-summary", action="store_true")
        if name == "run":
            command.add_argument("--no-cache", action="store_true")
            command.add_argument("--max-workers", type=int, default=None)
    return parser


def _planner_hint(ns: argparse.Namespace) -> PlannerHint:
    return PlannerHint(
        profile=ns.profile,
        reasons=tuple(ns.reason or ()),
        changed_paths=tuple(ns.changed_path or ()),
        targeted=not bool(getattr(ns, "no_targeting", False)),
    )


def _print_legacy_summary(payload: dict[str, object]) -> None:
    print(f"[quality] final verdict contract: {payload['verdict_contract']}")
    profile_node = payload.get("profile")
    if isinstance(profile_node, dict):
        profile_used = profile_node.get("used") or profile_node.get("selected") or "unknown"
    else:
        profile_used = profile_node
    print(f"[quality] profile used: {profile_used}")
    checks_run = payload.get("checks_run")
    checks_skipped = payload.get("checks_skipped")
    print(f"[quality] checks run: {len(checks_run) if isinstance(checks_run, list) else 0}")
    print(
        f"[quality] checks skipped: {len(checks_skipped) if isinstance(checks_skipped, list) else 0}"
    )
    blocking = payload.get("blocking_failures", [])
    if isinstance(blocking, list) and blocking:
        print("[quality] blocking failures:")
        for item in blocking:
            print(f"- {item}")
    else:
        print("[quality] blocking failures: none")
    advisory = payload.get("advisory_findings", [])
    if isinstance(advisory, list) and advisory:
        print("[quality] advisory findings:")
        for item in advisory:
            print(f"- {item}")
    else:
        print("[quality] advisory findings: none")
    confidence = payload.get("confidence_level", payload.get("confidence", "unknown"))
    print(f"[quality] confidence level: {confidence}")
    print(f"[quality] merge/release recommendation: {payload['recommendation']}")
    metadata = payload.get("metadata", {})
    if isinstance(metadata, dict):
        execution = metadata.get("execution", payload.get("execution", {}))
        if isinstance(execution, dict):
            print(
                f"[quality] execution: {execution.get('mode', 'sequential')} with {execution.get('workers', 1)} worker(s)"
            )
        json_out = metadata.get("json_output")
        md_out = metadata.get("markdown_output")
        if json_out:
            print(f"[quality] verdict json: {json_out}")
        if md_out:
            print(f"[quality] summary md: {md_out}")
        fix_plan_out = metadata.get("fix_plan_output")
        risk_summary_out = metadata.get("risk_summary_output")
        evidence_out = metadata.get("evidence_output")
        if fix_plan_out:
            print(f"[quality] fix plan json: {fix_plan_out}")
        if risk_summary_out:
            print(f"[quality] risk summary json: {risk_summary_out}")
        if evidence_out:
            print(f"[quality] evidence zip: {evidence_out}")


def _artifact_paths(ns: argparse.Namespace, out_dir: Path) -> ArtifactPaths:
    defaults = artifact_paths_for(out_dir)
    return ArtifactPaths(
        verdict_json=Path(ns.json_output) if ns.json_output else defaults.verdict_json,
        summary_md=Path(ns.markdown_output) if ns.markdown_output else defaults.summary_md,
        fix_plan_json=Path(ns.fix_plan_output) if ns.fix_plan_output else defaults.fix_plan_json,
        risk_summary_json=Path(ns.risk_summary_output)
        if ns.risk_summary_output
        else defaults.risk_summary_json,
        evidence_zip=Path(ns.evidence_output) if ns.evidence_output else defaults.evidence_zip,
        run_report_json=Path(ns.run_report_output)
        if ns.run_report_output
        else defaults.run_report_json,
    )


def _load_records_from_ledger(path: Path) -> tuple[CheckRecord, ...]:
    records: list[CheckRecord] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        item = json.loads(raw)
        status = cast(CheckStatus, str(item["status"]))
        records.append(
            CheckRecord(
                id=str(item["id"]),
                title=str(item["title"]),
                status=status,
                blocking=coerce_bool(item.get("blocking", True), default=True),
                reason=str(item.get("reason", "")),
                command=str(item.get("command") or item.get("cmd") or ""),
                advisory=tuple(str(entry) for entry in item.get("advisory", []) if str(entry)),
                log_path=str(item.get("log_path") or item.get("log") or ""),
                evidence_paths=tuple(
                    str(entry) for entry in item.get("evidence_paths", []) if str(entry)
                ),
                elapsed_seconds=float(item.get("elapsed_seconds") or item.get("elapsed_s") or 0.0),
                metadata=dict(item.get("metadata", {})),
            )
        )
    return tuple(records)


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    repo_root = Path(ns.repo_root).resolve()
    out_dir = Path(ns.out_dir).resolve()
    output_paths = _artifact_paths(ns, out_dir) if ns.cmd in {"run", "render-ledger"} else None
    registry = default_registry()
    if ns.cmd == "render-ledger":
        assert output_paths is not None
        metadata = json.loads(ns.metadata_json) if ns.metadata_json else {}
        payload = render_record_artifacts(
            repo_root=repo_root,
            out_dir=out_dir,
            profile=ns.profile,
            records=_load_records_from_ledger(Path(ns.ledger)),
            requested_profile=ns.requested_profile,
            profile_notes=ns.profile_notes,
            metadata=metadata,
            paths=output_paths,
        )
        verdict_payload = payload["verdict"]
        verdict_payload.setdefault("metadata", {})
        if isinstance(verdict_payload["metadata"], dict):
            verdict_payload["metadata"]["json_output"] = str(output_paths.verdict_json)
            verdict_payload["metadata"]["markdown_output"] = str(output_paths.summary_md)
            verdict_payload["metadata"]["fix_plan_output"] = str(output_paths.fix_plan_json)
            verdict_payload["metadata"]["risk_summary_output"] = str(output_paths.risk_summary_json)
            verdict_payload["metadata"]["evidence_output"] = str(output_paths.evidence_zip)
        if ns.format == "json":
            sys.stdout.write(json.dumps(verdict_payload, sort_keys=True, indent=2) + "\n")
        else:
            _print_legacy_summary(verdict_payload)
        if ns.emit_legacy_summary and ns.format == "json":
            _print_legacy_summary(verdict_payload)
        return 0 if verdict_payload["ok"] else 1

    planner = CheckPlanner(registry.snapshot())
    plan = planner.plan(ns.profile, repo_root=repo_root, hint=_planner_hint(ns))

    if ns.cmd == "plan":
        payload = {
            "profile": plan.profile,
            "requested_profile": plan.requested_profile,
            "planner_selected": plan.planner_selected,
            "selected_checks": [item.__dict__ for item in plan.selected_checks],
            "skipped_checks": [item.__dict__ for item in plan.skipped_checks],
            "notes": list(plan.notes),
            "changed_files": list(plan.changed_files),
            "changed_areas": list(plan.changed_areas),
            "adaptive_reason": plan.adaptive_reason,
        }
        if ns.format == "json":
            sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        else:
            print(f"profile: {plan.profile}")
            print(f"requested: {plan.requested_profile}")
            if plan.adaptive_reason:
                print(f"adaptive reason: {plan.adaptive_reason}")
            print("selected:")
            for item in plan.selected_checks:
                print(f"- {item.id} [{item.target_mode}]")
            print("skipped:")
            for skipped in plan.skipped_checks:
                print(f"- {skipped.id}: {skipped.reason}")
        return 0

    runner = CheckRunner(registry.snapshot())
    report = runner.run(
        plan,
        repo_root=repo_root,
        out_dir=out_dir,
        env=dict(os.environ),
        python_executable=sys.executable,
        use_cache=not ns.no_cache,
        max_workers=ns.max_workers,
    )
    verdict_payload = report.as_dict()
    assert output_paths is not None
    render_report_artifacts(report, repo_root=repo_root, out_dir=out_dir, paths=output_paths)
    verdict_payload.setdefault("metadata", {})
    if isinstance(verdict_payload["metadata"], dict):
        verdict_payload["metadata"]["json_output"] = str(output_paths.verdict_json)
        verdict_payload["metadata"]["markdown_output"] = str(output_paths.summary_md)
        verdict_payload["metadata"]["fix_plan_output"] = str(output_paths.fix_plan_json)
        verdict_payload["metadata"]["risk_summary_output"] = str(output_paths.risk_summary_json)
        verdict_payload["metadata"]["evidence_output"] = str(output_paths.evidence_zip)
        verdict_payload["metadata"]["run_report_output"] = str(output_paths.run_report_json)

    if ns.format == "json":
        sys.stdout.write(json.dumps(verdict_payload, sort_keys=True, indent=2) + "\n")
    else:
        _print_legacy_summary(verdict_payload)
    if ns.emit_legacy_summary and ns.format == "json":
        _print_legacy_summary(verdict_payload)
    return 0 if report.verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
