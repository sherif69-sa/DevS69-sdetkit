from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Step:
    id: str
    cmd: str


@dataclass(frozen=True)
class Profile:
    name: str
    steps: tuple[Step, ...]


REVIEW_CMD = "PYTHONPATH=src python -m sdetkit review . --no-workspace --format operator-json"

PROFILES: dict[str, Profile] = {
    "small": Profile(
        name="small",
        steps=(
            Step("lint", "ruff check ."),
            Step("format", "ruff format --check ."),
            Step("gate_fast", "PYTHONPATH=src python -m sdetkit gate fast"),
        ),
    ),
    "medium": Profile(
        name="medium",
        steps=(
            Step("lint", "ruff check ."),
            Step("format", "ruff format --check ."),
            Step("gate_fast", "PYTHONPATH=src python -m sdetkit gate fast"),
            Step("pytest", "PYTHONPATH=src pytest -q"),
            Step("gate_release", "PYTHONPATH=src python -m sdetkit gate release"),
            Step("review", REVIEW_CMD),
        ),
    ),
    "large": Profile(
        name="large",
        steps=(
            Step("lint", "ruff check ."),
            Step("format", "ruff format --check ."),
            Step("gate_fast", "PYTHONPATH=src python -m sdetkit gate fast"),
            Step("pytest", "PYTHONPATH=src pytest -q"),
            Step("gate_release", "PYTHONPATH=src python -m sdetkit gate release"),
            Step("doctor", "PYTHONPATH=src python -m sdetkit doctor"),
            Step("coverage", "bash quality.sh cov"),
            Step("review", REVIEW_CMD),
        ),
    ),
}


def _run_command(cmd: str) -> int:
    proc = subprocess.run(shlex.split(cmd), check=False)
    return int(proc.returncode)


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="PR cleanliness helper: run ordered check profiles and optionally execute them.",
    )
    p.add_argument("--size", choices=("small", "medium", "large"), default="small")
    p.add_argument(
        "--run",
        action="store_true",
        help="Execute profile steps. Without this flag, print plan/report only.",
    )
    p.add_argument(
        "--report",
        default=".sdetkit/pr-clean-report.json",
        help="Write plan/run report JSON to this path.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    profile = PROFILES[ns.size]

    print(f"pr-clean profile: {profile.name}")
    for i, step in enumerate(profile.steps, start=1):
        print(f"{i}. [{step.id}] {step.cmd}")

    report_path = Path(ns.report)
    report: dict[str, object] = {
        "profile": profile.name,
        "run": bool(ns.run),
        "ok": True,
        "steps": [
            {"id": step.id, "cmd": step.cmd, "rc": None, "ok": None} for step in profile.steps
        ],
    }

    if not ns.run:
        print("plan-only mode: use --run to execute steps")
        _write_report(report_path, report)
        return 0

    step_rows = report["steps"]
    assert isinstance(step_rows, list)

    for idx, step in enumerate(profile.steps):
        print(f"\n>>> [{step.id}] {step.cmd}")
        rc = _run_command(step.cmd)
        row = step_rows[idx]
        assert isinstance(row, dict)
        row["rc"] = rc
        row["ok"] = rc == 0
        if rc != 0:
            report["ok"] = False
            _write_report(report_path, report)
            print(f"failed: {step.cmd} (rc={rc})", file=sys.stderr)
            return rc

    _write_report(report_path, report)
    print("pr-clean passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
