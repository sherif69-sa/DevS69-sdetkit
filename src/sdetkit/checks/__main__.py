from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .base import PlannerHint
from .planner import CheckPlanner
from .registry import default_registry
from .runner import CheckRunner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.checks")
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name in ("plan", "run"):
        command = sub.add_parser(name)
        command.add_argument(
            "--profile", choices=["quick", "standard", "strict", "adaptive"], required=True
        )
        command.add_argument("--repo-root", default=".")
        command.add_argument("--out-dir", default=".sdetkit/out")
        command.add_argument("--changed-path", action="append", default=None)
        command.add_argument("--reason", action="append", default=None)
        command.add_argument("--format", choices=["json", "text"], default="json")
        if name == "run":
            command.add_argument("--json-output", default=None)
            command.add_argument("--markdown-output", default=None)
            command.add_argument("--emit-legacy-summary", action="store_true")
    return parser


def _planner_hint(ns: argparse.Namespace) -> PlannerHint:
    return PlannerHint(
        profile=ns.profile,
        reasons=tuple(ns.reason or ()),
        changed_paths=tuple(ns.changed_path or ()),
    )


def _print_legacy_summary(payload: dict[str, object]) -> None:
    print(f"[quality] final verdict contract: {payload['verdict_contract']}")
    print(f"[quality] profile used: {payload['profile']}")
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
    print(f"[quality] confidence level: {payload['confidence_level']}")
    print(f"[quality] merge/release recommendation: {payload['recommendation']}")
    metadata = payload.get("metadata", {})
    if isinstance(metadata, dict):
        json_out = metadata.get("json_output")
        md_out = metadata.get("markdown_output")
        if json_out:
            print(f"[quality] verdict json: {json_out}")
        if md_out:
            print(f"[quality] summary md: {md_out}")


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    repo_root = Path(ns.repo_root).resolve()
    out_dir = Path(ns.out_dir).resolve()
    registry = default_registry()
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
        }
        if ns.format == "json":
            sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        else:
            print(f"profile: {plan.profile}")
            print(f"requested: {plan.requested_profile}")
            print("selected:")
            for item in plan.selected_checks:
                print(f"- {item.id}")
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
    )
    verdict_payload = report.as_dict()

    json_output = ns.json_output or str(out_dir / "quality-verdict.json")
    markdown_output = ns.markdown_output or str(out_dir / "quality-summary.md")
    Path(json_output).write_text(report.verdict.to_json(), encoding="utf-8")
    Path(markdown_output).write_text(report.verdict.to_markdown(), encoding="utf-8")
    verdict_payload.setdefault("metadata", {})
    if isinstance(verdict_payload["metadata"], dict):
        verdict_payload["metadata"]["json_output"] = json_output
        verdict_payload["metadata"]["markdown_output"] = markdown_output

    if ns.format == "json":
        sys.stdout.write(json.dumps(verdict_payload, sort_keys=True, indent=2) + "\n")
    else:
        _print_legacy_summary(verdict_payload)
    if ns.emit_legacy_summary and ns.format == "json":
        _print_legacy_summary(verdict_payload)
    return 0 if report.verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
