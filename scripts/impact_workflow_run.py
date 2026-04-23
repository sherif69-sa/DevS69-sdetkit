from __future__ import annotations

import argparse
import json
import shlex
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class WorkflowStep:
    key: str
    name: str
    phase_alignment: tuple[int, int]
    commands: tuple[str, ...]


STEPS: tuple[WorkflowStep, ...] = (
    WorkflowStep(
        key="step_1",
        name="Impact Lock (Phases 1-2)",
        phase_alignment=(1, 2),
        commands=(
            "python -m sdetkit security scan --format sarif --output build/code-scanning.sarif --fail-on high",
            "python -m sdetkit gate release --format json > build/release-preflight.json",
        ),
    ),
    WorkflowStep(
        key="step_2",
        name="Impact Accelerate (Phases 3-4)",
        phase_alignment=(3, 4),
        commands=(
            "python -m sdetkit checks run --profile strict --format json --repo-root . --out-dir .sdetkit/out",
            "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json",
        ),
    ),
    WorkflowStep(
        key="step_3",
        name="Impact Prove (Phases 5-6)",
        phase_alignment=(5, 6),
        commands=(
            "python -m sdetkit doctor --release --format json --out build/doctor-release.json",
            "python scripts/build_top_tier_reporting_bundle.py",
        ),
    ),
)

BOOST_COMMANDS: tuple[str, ...] = (
    "bash quality.sh boost",
    "python scripts/impact_workflow_map.py",
)


def _parse_step(value: str) -> tuple[WorkflowStep, ...]:
    if value == "all":
        return STEPS
    for step in STEPS:
        if step.key == value:
            return (step,)
    raise ValueError(f"unknown step: {value}")


def _run_command(cmd: str) -> dict[str, object]:
    proc = subprocess.run(shlex.split(cmd), text=True, capture_output=True, check=False)
    return {
        "command": cmd,
        "rc": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def _completion(total: int, passed: int) -> float:
    if total <= 0:
        return 0.0
    return round((passed / total) * 100.0, 2)


def _step_readiness(step_key: str, command_results: list[dict[str, object]], step_ok: bool) -> dict[str, object]:
    if step_key == "step_1":
        return {
            "phase_1_security_scan_ok": command_results[0]["ok"] if command_results else False,
            "phase_2_release_gate_ok": command_results[1]["ok"] if len(command_results) > 1 else False,
            "phase_alignment_ok": step_ok,
        }
    if step_key == "step_2":
        return {
            "phase_3_strict_checks_ok": command_results[0]["ok"] if command_results else False,
            "phase_4_fast_gate_ok": command_results[1]["ok"] if len(command_results) > 1 else False,
            "phase_alignment_ok": step_ok,
        }
    if step_key == "step_3":
        return {
            "phase_5_release_doctor_ok": command_results[0]["ok"] if command_results else False,
            "phase_6_reporting_bundle_ok": command_results[1]["ok"] if len(command_results) > 1 else False,
            "phase_alignment_ok": step_ok,
        }
    return {"phase_alignment_ok": step_ok}


def _run_commands(commands: tuple[str, ...], dry_run: bool) -> list[dict[str, object]]:
    return [({"command": cmd, "rc": 0, "ok": True, "dry_run": True} if dry_run else _run_command(cmd)) for cmd in commands]


def _run_boost(dry_run: bool) -> dict[str, object]:
    commands = _run_commands(BOOST_COMMANDS, dry_run=dry_run)
    passed = sum(1 for cmd in commands if cmd["ok"])
    total = len(commands)
    return {
        "enabled": True,
        "ok": passed == total,
        "commands": commands,
        "passed_commands": passed,
        "total_commands": total,
        "completion_pct": _completion(total, passed),
    }


def run_workflow(selected_steps: tuple[WorkflowStep, ...], dry_run: bool, boost: bool) -> dict[str, object]:
    steps_payload: list[dict[str, object]] = []
    overall_ok = True
    overall_total = 0
    overall_passed = 0

    for step in selected_steps:
        command_results = _run_commands(step.commands, dry_run=dry_run)
        passed_commands = sum(1 for item in command_results if item["ok"])
        total_commands = len(command_results)
        step_ok = passed_commands == total_commands

        if not step_ok:
            overall_ok = False

        overall_total += total_commands
        overall_passed += passed_commands

        steps_payload.append(
            {
                "step": step.key,
                "name": step.name,
                "phase_alignment": list(step.phase_alignment),
                "ok": step_ok,
                "commands": command_results,
                "passed_commands": passed_commands,
                "total_commands": total_commands,
                "completion_pct": _completion(total_commands, passed_commands),
                "phase_readiness": _step_readiness(step.key, command_results, step_ok),
            }
        )

    boost_payload = {"enabled": False}
    if boost:
        boost_payload = _run_boost(dry_run=dry_run)
        overall_total += int(boost_payload["total_commands"])
        overall_passed += int(boost_payload["passed_commands"])
        if not boost_payload["ok"]:
            overall_ok = False

    return {
        "schema_version": "sdetkit.impact-workflow-run.v4",
        "ok": overall_ok,
        "dry_run": dry_run,
        "boost": boost_payload,
        "progress": {
            "passed_commands": overall_passed,
            "total_commands": overall_total,
            "completion_pct": _completion(overall_total, overall_passed),
        },
        "steps": steps_payload,
    }


def _render_follow_up(payload: dict[str, object]) -> str:
    lines = [
        "# Impact Workflow Follow-up",
        "",
        f"- Overall ok: `{payload['ok']}`",
        f"- Dry run: `{payload['dry_run']}`",
        f"- Completion: `{payload['progress']['completion_pct']}%`",
        "",
        "## Step Status",
    ]

    for step in payload["steps"]:
        lines.append(
            f"- **{step['step']}** `{step['name']}`: ok=`{step['ok']}` "
            f"completion=`{step['completion_pct']}%` ({step['passed_commands']}/{step['total_commands']})"
        )
        lines.append(f"  - phase_readiness: `{step['phase_readiness']}`")

    lines.extend(
        [
            "",
            "## Next Follow-up",
            "- Re-run failed commands first, then re-run the same step with `--format json --out`.",
            "- Keep the latest follow-up markdown artifact attached to your release evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_next_plan(payload: dict[str, object]) -> dict[str, object]:
    now: list[str] = []
    next_items: list[str] = []
    later: list[str] = []

    for step in payload["steps"]:
        if step["ok"]:
            next_items.append(f"Keep {step['step']} green and archive evidence.")
            continue
        now.append(f"Fix failing commands in {step['step']} and re-run the same step.")

    boost_payload = payload.get("boost", {"enabled": False})
    if boost_payload.get("enabled") and not boost_payload.get("ok", False):
        now.append("Boost lane has failures; re-run with --boost after fixing base step failures.")
    elif boost_payload.get("enabled"):
        next_items.append("Promote boost outputs into release evidence bundle.")

    if payload["ok"]:
        next_items.append("Run non-dry execution for the same scope and compare artifacts.")
        later.append("Automate this command in CI as required merge/release gate.")
    else:
        later.append("After stabilizing failures, run --step all --boost for full-system confidence.")

    return {
        "schema_version": "sdetkit.impact-next-plan.v1",
        "status": "ready" if payload["ok"] else "blocked",
        "now": now,
        "next": next_items,
        "later": later,
    }


def _build_adaptive_review(payload: dict[str, object]) -> dict[str, object]:
    steps = {step["step"]: step for step in payload["steps"]}
    step1 = steps.get("step_1", {"phase_readiness": {}})
    step2 = steps.get("step_2", {"phase_readiness": {}})
    step3 = steps.get("step_3", {"phase_readiness": {}})
    progress = float(payload["progress"]["completion_pct"])
    boost_ok = bool(payload.get("boost", {}).get("ok", False)) if payload.get("boost", {}).get("enabled") else True

    heads = {
        "security_head": {
            "score": 100 if step1["phase_readiness"].get("phase_1_security_scan_ok", False) else 40,
            "rationale": "Phase 1 security scan drives security readiness.",
        },
        "reliability_head": {
            "score": 100 if step1["phase_readiness"].get("phase_2_release_gate_ok", False) else 45,
            "rationale": "Release gate outcomes map directly to reliability confidence.",
        },
        "velocity_head": {
            "score": min(100, int(progress)),
            "rationale": "Execution completion indicates delivery velocity.",
        },
        "governance_head": {
            "score": 100 if step2["phase_readiness"].get("phase_3_strict_checks_ok", False) and boost_ok else 55,
            "rationale": "Strict checks and boost discipline reflect governance quality.",
        },
        "observability_head": {
            "score": 100 if step3["phase_readiness"].get("phase_6_reporting_bundle_ok", False) else 50,
            "rationale": "Reporting bundle health shows observability maturity.",
        },
    }

    avg = round(sum(item["score"] for item in heads.values()) / 5, 2)
    weakest_head = min(heads.items(), key=lambda kv: kv[1]["score"])[0]
    return {
        "schema_version": "sdetkit.impact-adaptive-review.v1",
        "overall_score": avg,
        "status": "strong" if avg >= 90 else "watch" if avg >= 70 else "critical",
        "weakest_head": weakest_head,
        "heads": heads,
    }


def _persist_intelligence_db(db_path: Path, payload: dict[str, object], review: dict[str, object]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS impact_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts TEXT NOT NULL,
              ok INTEGER NOT NULL,
              completion_pct REAL NOT NULL,
              boost_enabled INTEGER NOT NULL,
              boost_ok INTEGER NOT NULL,
              overall_score REAL NOT NULL,
              weakest_head TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS impact_head_scores (
              run_id INTEGER NOT NULL,
              head TEXT NOT NULL,
              score REAL NOT NULL,
              rationale TEXT NOT NULL,
              FOREIGN KEY(run_id) REFERENCES impact_runs(id)
            )
            """
        )
        cur = conn.execute(
            """
            INSERT INTO impact_runs (ts, ok, completion_pct, boost_enabled, boost_ok, overall_score, weakest_head)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(UTC).isoformat(),
                int(bool(payload["ok"])),
                float(payload["progress"]["completion_pct"]),
                int(bool(payload.get("boost", {}).get("enabled", False))),
                int(bool(payload.get("boost", {}).get("ok", False))),
                float(review["overall_score"]),
                str(review["weakest_head"]),
            ),
        )
        run_id = int(cur.lastrowid)
        for head, details in review["heads"].items():
            conn.execute(
                "INSERT INTO impact_head_scores (run_id, head, score, rationale) VALUES (?, ?, ?, ?)",
                (run_id, head, float(details["score"]), str(details["rationale"])),
            )




def _build_criteria_report(
    payload: dict[str, object],
    adaptive_review: dict[str, object],
    next_plan: dict[str, object],
    db_path: Path,
) -> dict[str, object]:
    checks: dict[str, dict[str, object]] = {}

    checks["adaptive_schema"] = {
        "ok": adaptive_review.get("schema_version") == "sdetkit.impact-adaptive-review.v1",
        "detail": str(adaptive_review.get("schema_version")),
    }
    checks["five_heads_present"] = {
        "ok": isinstance(adaptive_review.get("heads"), dict) and len(adaptive_review.get("heads", {})) == 5,
        "detail": f"heads={len(adaptive_review.get('heads', {})) if isinstance(adaptive_review.get('heads'), dict) else 0}",
    }
    checks["database_ready"] = {
        "ok": db_path.exists(),
        "detail": db_path.as_posix(),
    }
    checks["next_plan_shape"] = {
        "ok": all(isinstance(next_plan.get(k), list) for k in ("now", "next", "later")),
        "detail": "now/next/later list contract",
    }
    checks["agent_operational_readiness"] = {
        "ok": bool(payload.get("progress", {}).get("completion_pct", 0) >= 80),
        "detail": f"completion={payload.get('progress', {}).get('completion_pct', 0)}",
    }

    passed = sum(1 for c in checks.values() if c["ok"])
    total = len(checks)
    return {
        "schema_version": "sdetkit.impact-criteria-report.v1",
        "ok": passed == total,
        "passed": passed,
        "total": total,
        "completion_pct": _completion(total, passed),
        "checks": checks,
    }
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the 3-step impact workflow implementation.")
    parser.add_argument("--step", default="all", help="one of: all, step_1, step_2, step_3")
    parser.add_argument("--dry-run", action="store_true", help="print/record commands without executing them")
    parser.add_argument("--boost", action="store_true", help="run the boost lane after selected step(s)")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--out", help="optional path for json output")
    parser.add_argument("--follow-up-out", default="build/impact-follow-up.md")
    parser.add_argument("--next-plan-out", default="build/impact-next-plan.json")
    parser.add_argument("--adaptive-review-out", default="build/impact-adaptive-review.json")
    parser.add_argument("--intelligence-db", default="build/impact-intelligence.db")
    parser.add_argument("--criteria-out", default="build/impact-criteria-report.json")
    args = parser.parse_args(argv)

    try:
        selected_steps = _parse_step(args.step)
    except ValueError as exc:
        print(f"impact workflow run failed: {exc}", file=sys.stderr)
        return 2

    payload = run_workflow(selected_steps, dry_run=args.dry_run, boost=args.boost)

    follow_up_path = Path(args.follow_up_out)
    follow_up_path.parent.mkdir(parents=True, exist_ok=True)
    follow_up_path.write_text(_render_follow_up(payload), encoding="utf-8")

    next_plan = _build_next_plan(payload)
    next_plan_path = Path(args.next_plan_out)
    next_plan_path.parent.mkdir(parents=True, exist_ok=True)
    next_plan_path.write_text(json.dumps(next_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    adaptive_review = _build_adaptive_review(payload)
    adaptive_review_path = Path(args.adaptive_review_out)
    adaptive_review_path.parent.mkdir(parents=True, exist_ok=True)
    adaptive_review_path.write_text(json.dumps(adaptive_review, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    db_path = Path(args.intelligence_db)
    _persist_intelligence_db(db_path, payload, adaptive_review)

    criteria = _build_criteria_report(payload, adaptive_review, next_plan, db_path)
    criteria_path = Path(args.criteria_out)
    criteria_path.parent.mkdir(parents=True, exist_ok=True)
    criteria_path.write_text(json.dumps(criteria, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        text = json.dumps(payload, indent=2, sort_keys=True)
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text + "\n", encoding="utf-8")
        else:
            print(text)
    else:
        print(f"impact workflow run: ok={payload['ok']} completion={payload['progress']['completion_pct']}%")
        print(f"follow-up markdown: {follow_up_path}")
        print(f"next plan json: {next_plan_path}")
        print(f"adaptive review json: {adaptive_review_path}")
        print(f"intelligence db: {args.intelligence_db}")
        print(f"criteria report: {criteria_path}")
        print(f"5-head score: {adaptive_review['overall_score']} weakest={adaptive_review['weakest_head']}")

    return 0 if payload["ok"] or args.dry_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
