from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _normalize_gate_payload(payload: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = dict(payload)
    root = out.get("root")
    root_str = root if isinstance(root, str) else ""
    out["root"] = "<repo>"
    steps = out.get("steps")
    if isinstance(steps, list):
        new_steps: list[object] = []
        for s in steps:
            if isinstance(s, dict):
                sd: dict[str, object] = dict(s)
                sd.pop("duration_ms", None)
                cmd = sd.get("cmd")
                if isinstance(cmd, list):
                    new_cmd: list[object] = []
                    for tok in cmd:
                        if isinstance(tok, str):
                            if root_str and (tok == root_str or tok.startswith(root_str + "/")):
                                tok = tok.replace(root_str, "<repo>", 1)
                            if tok.startswith("/") and tok.rsplit("/", 1)[-1].startswith("python"):
                                tok = "python"
                        new_cmd.append(tok)
                    sd["cmd"] = new_cmd
                new_steps.append(sd)
            else:
                new_steps.append(s)
        out["steps"] = new_steps
    return out


def _stable_json(data: dict[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def _baseline_snapshot_path(root: Path) -> Path:
    return root / ".sdetkit" / "gate.fast.snapshot.json"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
    raw = list(argv) if argv is not None else None
    args0 = raw if raw is not None else list(sys.argv[1:])
    if args0 and args0[0] == "baseline":
        bp = argparse.ArgumentParser(prog="gate baseline")
        bp.add_argument("action", choices=["write", "check"])
        bp.add_argument("--path", default=None)
        ns, extra = bp.parse_known_args(args0[1:])
        if extra and extra[0] == "--":
            extra = extra[1:]

        root = Path.cwd()
        snap = (
            Path(ns.path) if isinstance(ns.path, str) and ns.path else _baseline_snapshot_path(root)
        )
        if not snap.is_absolute():
            snap = root / snap
        snap.parent.mkdir(parents=True, exist_ok=True)

        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc_fast = main(["fast", "--format", "json"] + list(extra))
        cur_text = buf.getvalue()
        if rc_fast != 0:
            return rc_fast

        try:
            cur_obj = json.loads(cur_text)
        except Exception:
            cur_obj = None

        if isinstance(cur_obj, dict):
            norm = _normalize_gate_payload(cur_obj)
            cur_text = _stable_json(norm)

        if ns.action == "write":
            snap.write_text(cur_text, encoding="utf-8")
            return 0

        snap_text = _read_text(snap) if snap.exists() else ""
        diff_ok = snap_text == cur_text
        try:
            out_obj = json.loads(cur_text)
            if isinstance(out_obj, dict):
                out_obj["snapshot_diff_ok"] = diff_ok
                out_obj["snapshot_diff_summary"] = [] if diff_ok else ["snapshot drift detected"]
                cur_text = _stable_json(out_obj)
        except Exception:
            pass
        sys.stdout.write(cur_text)
        return 0 if diff_ok else 2

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
