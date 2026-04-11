from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


CHECKS: tuple[tuple[str, list[str]], ...] = (
    (
        "repo_default",
        [
            sys.executable,
            "-m",
            "sdetkit",
            "repo",
            "check",
            "--format",
            "json",
            "--out",
            "build/repo-check-default.json",
            "--force",
        ],
    ),
    (
        "repo_enterprise",
        [
            sys.executable,
            "-m",
            "sdetkit",
            "repo",
            "check",
            "--profile",
            "enterprise",
            "--format",
            "json",
            "--out",
            "build/repo-check-enterprise.json",
            "--force",
        ],
    ),
    ("ruff", [sys.executable, "-m", "ruff", "check", "src", "tests"]),
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Unified guard for security + quality + review readiness.",
    )
    p.add_argument("--run", action="store_true", help="Execute checks. Without this flag, print plan only.")
    p.add_argument("--report", default="build/security-quality-review-guard.json")
    return p


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    report_path = Path(ns.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    print("security-quality-review-guard plan:")
    for idx, (name, cmd) in enumerate(CHECKS, start=1):
        print(f"{idx}. [{name}] {' '.join(cmd)}")
        rows.append({"id": name, "cmd": cmd, "rc": None, "ok": None})

    if not ns.run:
        payload = {"ok": True, "run": False, "checks": rows}
        report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print("plan-only mode: use --run to execute checks")
        return 0

    ok = True
    for row in rows:
        cmd = row["cmd"]
        assert isinstance(cmd, list)
        print("$", " ".join(cmd))
        proc = subprocess.run(cmd, check=False)
        rc = int(proc.returncode)
        row["rc"] = rc
        row["ok"] = rc == 0
        if rc != 0:
            ok = False
            break

    payload = {"ok": ok, "run": True, "checks": rows}
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
