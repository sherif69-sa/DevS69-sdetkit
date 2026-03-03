from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _run(cmd: list[str], cwd: Path) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    dur_ms = int((time.time() - started) * 1000)
    return {
        "cmd": cmd,
        "rc": proc.returncode,
        "ok": proc.returncode == 0,
        "duration_ms": dur_ms,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _write_output(text: str, out: str | None) -> None:
    if out:
        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _format_text(payload: dict[str, Any]) -> str:
    ok = bool(payload.get("ok"))
    lines: list[str] = []
    lines.append(f"gate fast: {'OK' if ok else 'FAIL'}")
    for step in payload.get("steps", []):
        marker = "OK" if step.get("ok") else "FAIL"
        dur = step.get("duration_ms", 0)
        step_id = step.get("id", "unknown")
        lines.append(f"[{marker}] {step_id} ({dur}ms) rc={step.get('rc')}")
    if payload.get("failed_steps"):
        lines.append("failed_steps:")
        for s in payload["failed_steps"]:
            lines.append(f"- {s}")
    return "\n".join(lines) + "\n"


def _format_md(payload: dict[str, Any]) -> str:
    ok = bool(payload.get("ok"))
    lines: list[str] = []
    lines.append("### SDET Gate Fast")
    lines.append("")
    lines.append(f"- status: {'OK' if ok else 'FAIL'}")
    lines.append(f"- root: `{payload.get('root', '')}`")
    lines.append("")
    lines.append("#### Steps")
    for step in payload.get("steps", []):
        marker = "OK" if step.get("ok") else "FAIL"
        dur = step.get("duration_ms", 0)
        step_id = step.get("id", "unknown")
        lines.append(f"- `{step_id}`: **{marker}** ({dur}ms, rc={step.get('rc')})")
    if payload.get("failed_steps"):
        lines.append("")
        lines.append("#### Failed steps")
        for s in payload["failed_steps"]:
            lines.append(f"- `{s}`")
    return "\n".join(lines) + "\n"


def _run_fast(ns: argparse.Namespace) -> int:
    root = Path(ns.root).resolve()

    steps: list[dict[str, Any]] = []

    if ns.fix or ns.fix_only:
        steps.append(
            {
                "id": "ruff_fix",
                **_run([sys.executable, "-m", "ruff", "check", "--fix", "."], cwd=root),
            }
        )
        steps.append(
            {
                "id": "ruff_format_apply",
                **_run([sys.executable, "-m", "ruff", "format", "."], cwd=root),
            }
        )
        if ns.fix_only:
            ns.no_doctor = True
            ns.no_ci_templates = True
            ns.no_ruff = True
            ns.no_mypy = True
            ns.no_pytest = True

    if not ns.no_doctor:
        fail_on = "medium" if ns.strict else "high"
        steps.append(
            {
                "id": "doctor",
                **_run(
                    [
                        sys.executable,
                        "-m",
                        "sdetkit",
                        "doctor",
                        "--dev",
                        "--ci",
                        "--deps",
                        "--clean-tree",
                        "--repo",
                        "--fail-on",
                        fail_on,
                        "--format",
                        "json",
                    ],
                    cwd=root,
                ),
            }
        )

    if not ns.no_ci_templates:
        steps.append(
            {
                "id": "ci_templates",
                **_run(
                    [
                        sys.executable,
                        "-m",
                        "sdetkit",
                        "ci",
                        "validate-templates",
                        "--root",
                        str(root),
                        "--format",
                        "json",
                        "--strict",
                    ],
                    cwd=root,
                ),
            }
        )

    if not ns.no_ruff:
        steps.append(
            {
                "id": "ruff",
                **_run([sys.executable, "-m", "ruff", "check", "."], cwd=root),
            }
        )
        steps.append(
            {
                "id": "ruff_format",
                **_run([sys.executable, "-m", "ruff", "format", "--check", "."], cwd=root),
            }
        )

    if not ns.no_mypy:
        mypy_args = ["src"]
        if ns.mypy_args:
            mypy_args = shlex.split(ns.mypy_args)
        steps.append(
            {
                "id": "mypy",
                **_run([sys.executable, "-m", "mypy", *mypy_args], cwd=root),
            }
        )

    if not ns.no_pytest:
        pytest_args = ["-q"]
        if ns.pytest_args:
            pytest_args = shlex.split(ns.pytest_args)
        steps.append(
            {
                "id": "pytest",
                **_run([sys.executable, "-m", "pytest", *pytest_args], cwd=root),
            }
        )

    failed = [s["id"] for s in steps if not s.get("ok", False)]
    payload: dict[str, Any] = {
        "profile": "fast",
        "root": str(root),
        "ok": not bool(failed),
        "failed_steps": failed,
        "steps": steps,
    }

    if ns.format == "json":
        rendered = json.dumps(payload, sort_keys=True) + "\n"
    elif ns.format == "md":
        rendered = _format_md(payload)
    else:
        rendered = _format_text(payload)

    _write_output(rendered, ns.out)

    if payload["ok"]:
        return 0
    sys.stderr.write("gate: problems found\n")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    fast = sub.add_parser("fast")
    fast.add_argument("--root", default=".")
    fast.add_argument("--format", choices=["text", "json", "md"], default="text")
    fast.add_argument("--out", "--output", default=None)
    fast.add_argument("--strict", action="store_true")

    fast.add_argument("--fix", action="store_true")
    fast.add_argument("--fix-only", dest="fix_only", action="store_true")

    fast.add_argument("--no-doctor", action="store_true")
    fast.add_argument("--no-ci-templates", action="store_true")
    fast.add_argument("--no-ruff", action="store_true")
    fast.add_argument("--no-mypy", action="store_true")
    fast.add_argument("--no-pytest", action="store_true")

    fast.add_argument("--pytest-args", default=None)
    fast.add_argument("--mypy-args", default=None)

    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.cmd == "fast":
        return _run_fast(ns)

    sys.stderr.write("unknown gate command\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
