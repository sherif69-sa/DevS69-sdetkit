from __future__ import annotations

import argparse
import difflib
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

AVAILABLE_STEPS = [
    "ruff_fix",
    "ruff_format_apply",
    "doctor",
    "ci_templates",
    "ruff",
    "ruff_format",
    "mypy",
    "pytest",
]

FAST_DEFAULT_PYTEST_ARGS = [
    "-q",
    "tests/test_gate_fast.py",
    "tests/test_gate_baseline.py",
    "tests/test_doctor_surgical.py",
    "tests/test_baseline_umbrella.py",
]


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
                sd.pop("stdout", None)
                sd.pop("stderr", None)
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


def _parse_step_filter(raw: str | None) -> set[str]:
    if not raw:
        return set()
    items = [part.strip() for part in raw.split(",")]
    return {item for item in items if item}


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
    only = _parse_step_filter(ns.only)
    skip = _parse_step_filter(ns.skip)

    unknown = sorted((only | skip) - set(AVAILABLE_STEPS))
    if unknown:
        sys.stderr.write(f"gate: unknown step id(s): {', '.join(unknown)}\n")
        return 2

    if ns.list_steps:
        sys.stdout.write("\n".join(AVAILABLE_STEPS) + "\n")
        return 0

    def should_run(step_id: str) -> bool:
        if only and step_id not in only:
            return False
        return step_id not in skip

    steps: list[dict[str, Any]] = []

    if (ns.fix or ns.fix_only) and should_run("ruff_fix"):
        steps.append(
            {
                "id": "ruff_fix",
                **_run([sys.executable, "-m", "ruff", "check", "--fix", "."], cwd=root),
            }
        )
    if (ns.fix or ns.fix_only) and should_run("ruff_format_apply"):
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

    if not ns.no_doctor and should_run("doctor"):
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

    if not ns.no_ci_templates and should_run("ci_templates"):
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

    if not ns.no_ruff and should_run("ruff"):
        steps.append(
            {
                "id": "ruff",
                **_run([sys.executable, "-m", "ruff", "check", "."], cwd=root),
            }
        )
    if not ns.no_ruff and should_run("ruff_format"):
        steps.append(
            {
                "id": "ruff_format",
                **_run([sys.executable, "-m", "ruff", "format", "--check", "."], cwd=root),
            }
        )

    if not ns.no_mypy and should_run("mypy"):
        mypy_args = ["src"]
        if ns.mypy_args:
            mypy_args = shlex.split(ns.mypy_args)
        steps.append(
            {
                "id": "mypy",
                **_run([sys.executable, "-m", "mypy", *mypy_args], cwd=root),
            }
        )

    if not ns.no_pytest and should_run("pytest"):
        pytest_args = list(FAST_DEFAULT_PYTEST_ARGS)
        if ns.full_pytest:
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


def _normalize_release_cmd(cmd: list[str], root: Path) -> list[str]:
    root_str = str(root)
    out: list[str] = []
    for tok in cmd:
        if tok == sys.executable:
            out.append("python")
            continue
        if tok == root_str or tok.startswith(root_str + "/"):
            out.append(tok.replace(root_str, "<repo>", 1))
            continue
        out.append(tok)
    return out


def _playbooks_validate_args(ns: argparse.Namespace) -> list[str]:
    args = ["--format", "json"]
    if getattr(ns, "playbooks_all", False):
        return ["--all", *args]
    if getattr(ns, "playbooks_legacy", False):
        return ["--legacy", *args]
    if getattr(ns, "playbooks_aliases", False):
        return ["--aliases", *args]

    names = list(getattr(ns, "playbook_name", []) or [])
    if names:
        out: list[str] = []
        for name in names:
            out.extend(["--name", name])
        return [*out, *args]

    return ["--recommended", *args]


def _format_release_text(payload: dict[str, Any]) -> str:
    lines = [f"gate release: {'OK' if payload.get('ok') else 'FAIL'}"]
    for step in payload.get("steps", []):
        status = "DRY" if step.get("dry_run") else ("OK" if step.get("ok") else "FAIL")
        lines.append(f"[{status}] {step.get('id')} rc={step.get('rc')}")
    if payload.get("failed_steps"):
        lines.append("failed_steps:")
        for item in payload["failed_steps"]:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _run_release(ns: argparse.Namespace) -> int:
    root = Path(ns.root).resolve()
    doctor_cmd = [sys.executable, "-m", "sdetkit", "doctor", "--release", "--format", "json"]
    if ns.release_full:
        doctor_cmd = [
            sys.executable,
            "-m",
            "sdetkit",
            "doctor",
            "--release-full",
            "--format",
            "json",
        ]

    commands: list[tuple[str, list[str]]] = [
        ("doctor_release", doctor_cmd),
        (
            "playbooks_validate",
            [
                sys.executable,
                "-m",
                "sdetkit",
                "playbooks",
                "validate",
                *_playbooks_validate_args(ns),
            ],
        ),
        (
            "gate_fast",
            [
                sys.executable,
                "-m",
                "sdetkit",
                "gate",
                "fast",
                "--root",
                str(root),
                "--format",
                "json",
            ],
        ),
    ]

    steps: list[dict[str, Any]] = []
    for step_id, cmd in commands:
        if ns.dry_run:
            steps.append({"id": step_id, "cmd": cmd, "dry_run": True, "rc": None, "ok": True})
        else:
            steps.append({"id": step_id, **_run(cmd, cwd=root)})

    failed = [s["id"] for s in steps if not s.get("ok", False)]
    for step in steps:
        step_cmd = step.get("cmd")
        if isinstance(step_cmd, list):
            step["cmd"] = _normalize_release_cmd([str(t) for t in step_cmd], root)

    payload = {
        "profile": "release",
        "root": "<repo>",
        "dry_run": bool(ns.dry_run),
        "ok": not bool(failed),
        "failed_steps": failed,
        "steps": steps,
    }

    rendered = (
        json.dumps(payload, sort_keys=True) + "\n"
        if ns.format == "json"
        else _format_release_text(payload)
    )
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
        bp.add_argument("--diff", action="store_true")
        bp.add_argument("--diff-context", type=int, default=3)
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

        diff_payload = ""
        if getattr(ns, "diff", False) and not diff_ok:
            n = int(getattr(ns, "diff_context", 3) or 0)
            n = n if n >= 0 else 0
            a = snap_text
            b = cur_text
            try:
                ao = json.loads(a)
                a = json.dumps(ao, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
            except json.JSONDecodeError:
                a = snap_text
            try:
                bo = json.loads(b)
                b = json.dumps(bo, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
            except json.JSONDecodeError:
                b = cur_text
            diff_lines = difflib.unified_diff(
                a.splitlines(keepends=True),
                b.splitlines(keepends=True),
                fromfile="snapshot",
                tofile="current",
                n=n,
            )
            diff_payload = "".join(diff_lines)
            if diff_payload and not diff_payload.endswith("\n"):
                diff_payload += "\n"
        out_obj: dict[str, object] | None = None
        try:
            parsed = json.loads(cur_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            out_obj = parsed
        if out_obj is not None:
            out_obj["snapshot_diff_ok"] = diff_ok
            if diff_ok:
                out_obj["snapshot_diff_summary"] = []
            else:
                summary = ["snapshot drift detected"]
                if not snap.exists():
                    summary.append("snapshot file missing")
                out_obj["snapshot_diff_summary"] = summary
            if diff_payload:
                out_obj["snapshot_diff"] = diff_payload
            cur_text = _stable_json(out_obj)
        sys.stdout.write(cur_text)
        return 0 if diff_ok else 2

    parser = argparse.ArgumentParser(prog="gate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    fast = sub.add_parser("fast")
    fast.add_argument("--root", default=".")
    fast.add_argument("--format", choices=["text", "json", "md"], default="text")
    fast.add_argument("--out", "--output", default=None)
    fast.add_argument("--strict", action="store_true")
    fast.add_argument("--list-steps", action="store_true")
    fast.add_argument("--only", default=None)
    fast.add_argument("--skip", default=None)

    fast.add_argument("--fix", action="store_true")
    fast.add_argument("--fix-only", dest="fix_only", action="store_true")

    fast.add_argument("--no-doctor", action="store_true")
    fast.add_argument("--no-ci-templates", action="store_true")
    fast.add_argument("--no-ruff", action="store_true")
    fast.add_argument("--no-mypy", action="store_true")
    fast.add_argument("--no-pytest", action="store_true")

    fast.add_argument("--pytest-args", default=None)
    fast.add_argument("--full-pytest", action="store_true")
    fast.add_argument("--mypy-args", default=None)

    release = sub.add_parser("release")
    release.add_argument("--root", default=".")
    release.add_argument("--format", choices=["text", "json"], default="text")
    release.add_argument("--out", "--output", default=None)
    release.add_argument("--dry-run", action="store_true")
    release.add_argument("--release-full", action="store_true")
    playbook_group = release.add_mutually_exclusive_group()
    playbook_group.add_argument("--playbooks-all", action="store_true")
    playbook_group.add_argument("--playbooks-legacy", action="store_true")
    playbook_group.add_argument("--playbooks-aliases", action="store_true")
    release.add_argument("--playbook-name", action="append", default=[])

    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.cmd == "fast":
        return _run_fast(ns)
    if ns.cmd == "release":
        return _run_release(ns)

    sys.stderr.write("unknown gate command\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
