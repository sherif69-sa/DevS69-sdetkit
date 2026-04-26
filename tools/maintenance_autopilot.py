from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run(cmd: list[str], *, allow_fail: bool = False, env: dict[str, str] | None = None) -> dict[str, Any]:
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
    if dry_summary["keep_open_count"] + dry_summary["defer_count"] != dry_summary["total_bot_trackers"]:
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
        "## Live run",
        f"- attempted: **{report['live_run']['attempted']}**",
        f"- executed: **{report['live_run']['executed']}**",
    ]
    if not report["live_run"]["executed"] and "reason" in report["live_run"]:
        md.append(f"- reason: `{report['live_run']['reason']}`")
    (out_dir / "autopilot-report.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")

    print(f"json: {out_dir / 'autopilot-report.json'}")
    print(f"markdown: {out_dir / 'autopilot-report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
