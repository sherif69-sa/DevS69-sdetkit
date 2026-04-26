from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _run(
    cmd: list[str], *, allow_fail: bool = False, env: dict[str, str] | None = None
) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    result = {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "ok": proc.returncode == 0,
    }
    if not allow_fail and proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    return result


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except ValueError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


POLICY_ACTIONS: dict[str, list[str]] = {
    "baseline_pre_commit": ["python -m pre_commit run -a"],
    "baseline_kpi_test": ["PYTHONPATH=src python -m pytest -q tests/test_kpi_audit.py"],
    "baseline_ruff": ["ruff check src/sdetkit/kpi_audit.py tools/maintenance_command_center.py"],
    "enterprise_repo_check": [
        "PYTHONPATH=src python -m sdetkit repo check . --profile enterprise --format json --force"
    ],
    "security_actionable": [
        "PYTHONPATH=src python -m sdetkit security check --root . --format json"
    ],
    "review_json": ["PYTHONPATH=src python -m sdetkit review . --no-workspace --format json"],
}

SAFE_AUTOREMEDIATE_KEYS = {"baseline_pre_commit", "baseline_ruff"}


def _summary_from_plan(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    keep_open = payload.get("keep_open", [])
    defer = payload.get("defer", [])
    return {
        "command_center_issue": payload.get("command_center_issue"),
        "total_bot_trackers": payload.get("total_bot_trackers", 0),
        "keep_open_count": len(keep_open) if isinstance(keep_open, list) else 0,
        "defer_count": len(defer) if isinstance(defer, list) else 0,
        "keep_open_numbers": [
            item.get("number") for item in keep_open if isinstance(item, dict) and "number" in item
        ],
        "defer_numbers": [
            item.get("number") for item in defer if isinstance(item, dict) and "number" in item
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fully automated maintenance command-center autopilot: baseline checks, enterprise gate, "
            "dry-run validation, and optional live execution."
        )
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out-dir", default="build/maintenance/autopilot")
    parser.add_argument("--run-live-if-token", action="store_true")
    parser.add_argument("--token-env", default="GH_TOKEN")
    parser.add_argument("--memory-db", default=".sdetkit/maintenance/failure-memory.jsonl")
    parser.add_argument("--auto-remediate-safe", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "schema_version": "sdetkit.maintenance.autopilot.v1",
        "owner": args.owner,
        "repo": args.repo,
        "steps": {},
    }

    # 1) Baseline checks
    report["steps"]["baseline_pre_commit"] = _run([sys.executable, "-m", "pre_commit", "run", "-a"])
    report["steps"]["baseline_kpi_test"] = _run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_kpi_audit.py"],
        env={**os.environ, "PYTHONPATH": "src"},
    )
    report["steps"]["baseline_ruff"] = _run(
        ["ruff", "check", "src/sdetkit/kpi_audit.py", "tools/maintenance_command_center.py"]
    )
    report["steps"]["baseline_security_check"] = _run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "security",
            "check",
            "--root",
            ".",
            "--format",
            "json",
            "--out",
            str(out_dir / "security-check.json"),
        ],
        env={**os.environ, "PYTHONPATH": "src"},
    )

    # 2) Enterprise gate
    shutil.rmtree(".sdetkit/cache", ignore_errors=True)
    shutil.rmtree(".sdetkit/ops-artifacts", ignore_errors=True)
    report["steps"]["enterprise_repo_check"] = _run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "repo",
            "check",
            ".",
            "--profile",
            "enterprise",
            "--format",
            "json",
            "--out",
            str(out_dir / "sdet_check.json"),
            "--force",
        ],
        env={**os.environ, "PYTHONPATH": "src"},
    )
    sdet_payload = _load_json(out_dir / "sdet_check.json")
    findings = int(sdet_payload.get("summary", {}).get("findings", -1))
    if findings != 0:
        raise RuntimeError(f"enterprise repo check findings expected 0, got {findings}")

    # 3) Build inputs + dry run
    doctor_json = out_dir / "doctor.json"
    review_json = out_dir / "review.json"
    report["steps"]["doctor_json"] = _run(
        [sys.executable, "-m", "sdetkit", "doctor", "--format", "json", "--out", str(doctor_json)],
        allow_fail=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    review_run = _run(
        [sys.executable, "-m", "sdetkit", "review", ".", "--no-workspace", "--format", "json"],
        allow_fail=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    review_json.write_text(review_run.get("stdout", ""), encoding="utf-8")
    report["steps"]["review_json"] = review_run

    dry_plan = out_dir / "command-center-dry-run-plan.json"
    report["steps"]["command_center_dry_run"] = _run(
        [
            sys.executable,
            "tools/maintenance_command_center.py",
            "--owner",
            args.owner,
            "--repo",
            args.repo,
            "--dry-run",
            "--doctor-json",
            str(doctor_json),
            "--review-json",
            str(review_json),
            "--plan-out",
            str(dry_plan),
            "--db-path",
            str(out_dir / "issue-learning-db.jsonl"),
            "--rollup-path",
            str(out_dir / "issue-learning-rollup.json"),
        ]
    )
    dry_summary = _summary_from_plan(dry_plan)
    report["dry_run_summary"] = dry_summary

    if dry_summary["total_bot_trackers"] <= 0:
        raise RuntimeError("dry run returned no bot trackers")
    if (
        dry_summary["keep_open_count"] + dry_summary["defer_count"]
        != dry_summary["total_bot_trackers"]
    ):
        raise RuntimeError("dry run keep/defer counts do not match total_bot_trackers")

    # 4) Optional live run
    token = os.getenv(args.token_env, "")
    report["live_run"] = {"attempted": False, "executed": False, "token_env": args.token_env}
    if args.run_live_if_token:
        report["live_run"]["attempted"] = True
        if token:
            live_plan = out_dir / "command-center-live-plan.json"
            report["steps"]["command_center_live_run"] = _run(
                [
                    sys.executable,
                    "tools/maintenance_command_center.py",
                    "--owner",
                    args.owner,
                    "--repo",
                    args.repo,
                    "--doctor-json",
                    str(doctor_json),
                    "--review-json",
                    str(review_json),
                    "--plan-out",
                    str(live_plan),
                    "--db-path",
                    ".sdetkit/maintenance/issue-learning-db.jsonl",
                    "--rollup-path",
                    ".sdetkit/maintenance/issue-learning-rollup.json",
                    "--token",
                    token,
                ]
            )
            report["live_run"]["executed"] = True
            report["live_run"]["summary"] = _summary_from_plan(live_plan)
        else:
            report["live_run"]["reason"] = f"missing token in env var {args.token_env}"

    security_payload = _load_json(out_dir / "security-check.json")
    security_counts = (
        security_payload.get("counts", {}) if isinstance(security_payload, dict) else {}
    )
    warn_count = int(security_counts.get("warn", 0) or 0)
    error_count = int(security_counts.get("error", 0) or 0)
    report["security"] = {
        "warn": warn_count,
        "error": error_count,
        "actionable_findings": warn_count + error_count,
        "follow_up_required": (warn_count + error_count) > 0,
    }

    observed_failures: list[dict[str, Any]] = []
    for step_name, step_payload in report.get("steps", {}).items():
        if not isinstance(step_payload, dict):
            continue
        if bool(step_payload.get("ok", True)):
            continue
        observed_failures.append(
            {
                "failure_key": step_name,
                "returncode": step_payload.get("returncode"),
                "policy_actions": POLICY_ACTIONS.get(step_name, []),
            }
        )
    if report["security"]["follow_up_required"]:
        observed_failures.append(
            {
                "failure_key": "security_actionable",
                "returncode": 1,
                "policy_actions": POLICY_ACTIONS.get("security_actionable", []),
            }
        )

    memory_db = Path(args.memory_db)
    run_id = datetime.now(UTC).isoformat()
    for item in observed_failures:
        _append_jsonl(
            memory_db,
            {
                "run_id": run_id,
                "owner": args.owner,
                "repo": args.repo,
                **item,
            },
        )

    history = _read_jsonl(memory_db)
    score: dict[str, int] = {}
    for item in history[-500:]:
        key = str(item.get("failure_key", "")).strip()
        if not key:
            continue
        score[key] = score.get(key, 0) + 1
    top_now = sorted(score.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
    report["follow_up"] = {
        "observed_failures_this_run": observed_failures,
        "memory_db": str(memory_db),
        "top_now": [
            {"failure_key": key, "seen_runs": count, "policy_actions": POLICY_ACTIONS.get(key, [])}
            for key, count in top_now
        ],
        "auto_remediation": [],
    }

    if args.auto_remediate_safe and observed_failures:
        remediation_results: list[dict[str, Any]] = []
        for item in observed_failures:
            key = str(item.get("failure_key", "")).strip()
            if key not in SAFE_AUTOREMEDIATE_KEYS:
                remediation_results.append(
                    {
                        "failure_key": key,
                        "attempted": False,
                        "reason": "not in SAFE_AUTOREMEDIATE_KEYS",
                    }
                )
                continue
            actions = POLICY_ACTIONS.get(key, [])
            if not actions:
                remediation_results.append(
                    {
                        "failure_key": key,
                        "attempted": False,
                        "reason": "no policy actions configured",
                    }
                )
                continue
            cmd = actions[0]
            env = {**os.environ, "PYTHONPATH": "src"}
            result = _run(shlex.split(cmd), allow_fail=True, env=env)
            remediation_results.append(
                {
                    "failure_key": key,
                    "attempted": True,
                    "command": cmd,
                    "ok": bool(result.get("ok", False)),
                    "returncode": result.get("returncode"),
                }
            )
        report["follow_up"]["auto_remediation"] = remediation_results

    _write_json(out_dir / "autopilot-report.json", report)

    md = [
        "# Maintenance autopilot report",
        "",
        f"- owner/repo: `{args.owner}/{args.repo}`",
        f"- dry-run total trackers: **{dry_summary['total_bot_trackers']}**",
        f"- dry-run keep_open: **{dry_summary['keep_open_count']}**",
        f"- dry-run defer: **{dry_summary['defer_count']}**",
        f"- dry-run keep_open numbers: `{dry_summary['keep_open_numbers']}`",
        f"- dry-run defer numbers: `{dry_summary['defer_numbers']}`",
        "",
        "## Security",
        f"- warn: **{warn_count}**",
        f"- error: **{error_count}**",
        f"- actionable findings: **{warn_count + error_count}**",
        f"- follow-up required: **{(warn_count + error_count) > 0}**",
        "",
        "## Failure memory + policy follow-up",
        f"- memory db: `{memory_db}`",
        f"- observed failures this run: **{len(observed_failures)}**",
        "- top recurring failure keys:",
    ]
    for item in report["follow_up"]["top_now"]:
        md.append(f"  - `{item['failure_key']}` seen {item['seen_runs']} run(s)")
        for action in item.get("policy_actions", []):
            md.append(f"    - auto-policy: `{action}`")
    md.append("- auto-remediation attempts:")
    for item in report["follow_up"].get("auto_remediation", []):
        if not item.get("attempted"):
            md.append(
                f"  - `{item.get('failure_key', 'unknown')}` skipped ({item.get('reason', 'n/a')})"
            )
            continue
        md.append(
            f"  - `{item.get('failure_key', 'unknown')}` attempted: ok={item.get('ok')} rc={item.get('returncode')}"
        )
    md.extend(
        [
            "",
            "## Live run",
            f"- attempted: **{report['live_run']['attempted']}**",
            f"- executed: **{report['live_run']['executed']}**",
        ]
    )
    if not report["live_run"]["executed"] and "reason" in report["live_run"]:
        md.append(f"- reason: `{report['live_run']['reason']}`")
    (out_dir / "autopilot-report.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")

    print(f"json: {out_dir / 'autopilot-report.json'}")
    print(f"markdown: {out_dir / 'autopilot-report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
