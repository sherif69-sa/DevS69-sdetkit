from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Callable, Sequence
from contextlib import redirect_stderr, redirect_stdout


def run_baseline(
    args: Sequence[str],
    *,
    doctor_main: Callable[[list[str]], int] | None = None,
    gate_main: Callable[[list[str]], int] | None = None,
) -> int:
    bp = argparse.ArgumentParser(prog="sdetkit baseline")
    bp.add_argument("action", choices=["write", "check"])
    bp.add_argument("--format", choices=["text", "json"], default="text")
    bp.add_argument("--diff", action="store_true")
    bp.add_argument("--diff-context", type=int, default=3)
    bns, extra = bp.parse_known_args(list(args))
    if extra and extra[0] == "--":
        extra = extra[1:]

    if doctor_main is None or gate_main is None:
        from sdetkit import doctor, gate

        doctor_main = doctor.main
        gate_main = gate.main

    steps: list[dict[str, object]] = []
    failed: list[str] = []

    diff_args: list[str] = []
    if getattr(bns, "diff", False):
        diff_args.append("--diff")
        diff_args.extend(["--diff-context", str(getattr(bns, "diff_context", 3))])
    for sid, fn in [
        ("doctor_baseline", doctor_main),
        ("gate_baseline", gate_main),
    ]:
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            rc = fn(["baseline", bns.action] + diff_args + (["--"] + extra if extra else []))
        step = {
            "id": sid,
            "rc": rc,
            "ok": rc == 0,
            "stdout": buf_out.getvalue(),
            "stderr": buf_err.getvalue(),
        }
        steps.append(step)
        if rc != 0:
            failed.append(sid)

    ok = not failed
    payload: dict[str, object] = {"ok": ok, "steps": steps, "failed_steps": failed}
    if bns.format == "json":
        sys.stdout.write(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
        )
    else:
        lines: list[str] = []
        lines.append(f"baseline: {'OK' if ok else 'FAIL'}")
        for step in steps:
            marker = "OK" if step.get("ok") else "FAIL"
            lines.append(f"[{marker}] {step.get('id')} rc={step.get('rc')}")
        if failed:
            lines.append("failed_steps:")
            for item in failed:
                lines.append(f"- {item}")
        sys.stdout.write("\n".join(lines) + "\n")
    return 0 if ok else 2
