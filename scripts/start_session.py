from __future__ import annotations

import argparse
import subprocess
import sys


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Start-of-work helper: validate workflow contract and prepare PR-clean checks.",
    )
    p.add_argument("--size", choices=("small", "medium", "large"), default="small")
    p.add_argument(
        "--run",
        action="store_true",
        help="Execute the selected pr_clean profile after startup validation.",
    )
    return p


def _run(cmd: list[str]) -> int:
    print("$", " ".join(cmd))
    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)

    rc = _run([sys.executable, "scripts/check_workflow_contract.py"])
    if rc != 0:
        return rc

    pr_cmd = [
        sys.executable,
        "scripts/pr_clean.py",
        "--size",
        ns.size,
        "--report",
        ".sdetkit/start-session-pr-clean.json",
    ]
    if ns.run:
        pr_cmd.append("--run")

    rc = _run(pr_cmd)
    if rc != 0:
        return rc

    print("\nStartup flow is clean.")
    print("Next: implement your change, then rerun pr_clean with --run before opening PR.")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
