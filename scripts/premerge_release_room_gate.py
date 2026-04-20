#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _run(cmd: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    return {
        "cmd": cmd,
        "return_code": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def run_gate(repo_root: Path) -> dict[str, Any]:
    steps = [
        (
            "enterprise_assessment",
            [
                "python",
                "-m",
                "sdetkit",
                "enterprise-assessment",
                "--format",
                "json",
                "--production-profile",
            ],
        ),
        (
            "ship_readiness",
            [
                "python",
                "-m",
                "sdetkit",
                "ship-readiness",
                "--strict",
                "--format",
                "json",
                "--out-dir",
                "build/ship-readiness",
            ],
        ),
        (
            "enterprise_contract",
            [
                "python",
                "scripts/check_enterprise_assessment_contract.py",
                "--summary",
                "docs/artifacts/enterprise-assessment-pack/enterprise-assessment-summary.json",
                "--format",
                "json",
            ],
        ),
        (
            "ship_contract",
            [
                "python",
                "scripts/check_ship_readiness_contract.py",
                "--summary",
                "build/ship-readiness/ship-readiness-summary.json",
                "--format",
                "json",
            ],
        ),
        (
            "release_room_summary",
            [
                "python",
                "scripts/render_release_room_summary.py",
                "--ship-summary",
                "build/ship-readiness/ship-readiness-summary.json",
                "--enterprise-summary",
                "docs/artifacts/enterprise-assessment-pack/enterprise-assessment-summary.json",
                "--out",
                "build/release-room-summary.md",
            ],
        ),
    ]

    rows: list[dict[str, Any]] = []
    for step_id, cmd in steps:
        result = _run(cmd, repo_root)
        result["id"] = step_id
        rows.append(result)

    generated = {
        "enterprise_summary": (
            repo_root
            / "docs/artifacts/enterprise-assessment-pack/enterprise-assessment-summary.json"
        ).exists(),
        "ship_summary": (repo_root / "build/ship-readiness/ship-readiness-summary.json").exists(),
        "release_room_summary": (repo_root / "build/release-room-summary.md").exists(),
    }

    return {
        "schema_version": "sdetkit.premerge_release_room_gate.v1",
        "generated_at_utc": datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "steps": rows,
        "generated_artifacts": generated,
        "ok": all(step["ok"] for step in rows) and all(generated.values()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run pre-merge release-room gate checks.")
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--out", default="build/premerge-release-room-gate.json")
    parser.add_argument("--format", choices=["text", "json"], default="json")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve()
    payload = run_gate(repo_root)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print("premerge-release-room-gate")
        print(f"ok: {payload['ok']}")
        for row in payload["steps"]:
            status = "PASS" if row["ok"] else "FAIL"
            print(f"- [{status}] {row['id']} rc={row['return_code']}")

    if args.strict and not payload["ok"]:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
