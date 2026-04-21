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

from ..bools import coerce_bool

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
                            base = tok.rsplit("/", 1)[-1]
                            if "/" in tok and base.startswith("python"):
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


def _baseline_snapshot_path(root: Path, profile: str) -> Path:
    name = "gate.release.snapshot.json" if profile == "release" else "gate.fast.snapshot.json"
    return root / ".sdetkit" / name


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


def _load_json_payload(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"gate trend: expected JSON object in {path}")
    return payload


def _run_trend(ns: argparse.Namespace) -> int:
    baseline = _load_json_payload(str(ns.baseline))
    current = _load_json_payload(str(ns.current))

    baseline_ok = coerce_bool(baseline.get("ok"), default=False)
    current_ok = coerce_bool(current.get("ok"), default=False)
    baseline_failed = len(list(baseline.get("failed_steps", []) or []))
    current_failed = len(list(current.get("failed_steps", []) or []))

    payload = {
        "ok": True,
        "baseline": str(ns.baseline),
        "current": str(ns.current),
        "baseline_ok": baseline_ok,
        "current_ok": current_ok,
        "failed_steps_baseline": baseline_failed,
        "failed_steps_current": current_failed,
        "failed_steps_delta": current_failed - baseline_failed,
        "status_delta": "improved"
        if current_ok and not baseline_ok
        else "regressed"
        if baseline_ok and not current_ok
        else "unchanged",
    }
    if str(ns.format) == "json":
        _write_output(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n", ns.out)
        return 0

    lines = [
        "gate trend",
        f"baseline_ok={baseline_ok} current_ok={current_ok} status_delta={payload['status_delta']}",
        (
            "failed_steps "
            f"baseline={baseline_failed} current={current_failed} delta={payload['failed_steps_delta']}"
        ),
    ]
    _write_output("\n".join(lines) + "\n", ns.out)
    return 0


def _parse_step_filter(raw: str | None) -> set[str]:
    if not raw:
        return set()
    items = [part.strip() for part in raw.split(",")]
    return {item for item in items if item}


def _parse_context_entries(entries: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in entries or []:
        raw = str(entry).strip()
        if not raw:
            continue
        key, sep, value = raw.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"gate: invalid --work-context entry '{entry}' (expected KEY=VALUE)")
        out[key.strip()] = value.strip()
    return out


def _request_context(ns: argparse.Namespace) -> dict[str, Any]:
    return {
        "work_id": str(getattr(ns, "work_id", "") or "").strip(),
        "work_context": _parse_context_entries(list(getattr(ns, "work_context", []) or [])),
    }


def _format_text(payload: dict[str, Any]) -> str:
    ok = coerce_bool(payload.get("ok"), default=False)
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
    if payload.get("recommendations"):
        lines.append("recommendations:")
        for item in payload["recommendations"]:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _format_md(payload: dict[str, Any]) -> str:
    ok = coerce_bool(payload.get("ok"), default=False)
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
    if payload.get("recommendations"):
        lines.append("")
        lines.append("#### Recommendations")
        for item in payload["recommendations"]:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _contains_missing_module(step: dict[str, Any], module_name: str) -> bool:
    stderr = str(step.get("stderr", ""))
    stdout = str(step.get("stdout", ""))
    marker = f"No module named {module_name!r}"
    return marker in stderr or marker in stdout


def _fast_recommendations(steps: list[dict[str, Any]], failed_steps: list[str]) -> list[str]:
    recommendations: list[str] = []
    for step in steps:
        step_id = str(step.get("id", ""))
        if step_id not in failed_steps:
            continue
        if step_id in {
            "ruff_fix",
            "ruff_format_apply",
            "ruff",
            "ruff_format",
        } and _contains_missing_module(step, "ruff"):
            recommendations.append(
                "Ruff is missing in this environment. Install dev tooling: python -m pip install -e .[dev,test]."
            )
            continue
        if step_id == "mypy" and _contains_missing_module(step, "mypy"):
            recommendations.append(
                "Mypy is missing in this environment. Install dev tooling: python -m pip install -e .[dev,test]."
            )
            continue
        if step_id == "pytest" and _contains_missing_module(step, "pytest"):
            recommendations.append(
                "Pytest is missing in this environment. Install test tooling: python -m pip install -e .[test]."
            )
            continue
        if step_id == "doctor":
            recommendations.append(
                "Inspect doctor evidence first: python -m sdetkit doctor --format json --out build/doctor.json."
            )
            continue
        if step_id == "ci_templates":
            recommendations.append(
                "Validate your CI templates under templates/ci or skip this step with --skip ci_templates."
            )
            continue
    return list(dict.fromkeys(recommendations))


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

    try:
        request_context = _request_context(ns)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    selected_steps = [step_id for step_id in AVAILABLE_STEPS if should_run(step_id)]
    if not selected_steps:
        empty_payload: dict[str, Any] = {
            "profile": "fast",
            "root": str(root),
            "request_context": request_context,
            "ok": False,
            "steps": [],
            "failed_steps": ["configuration"],
            "recommendations": [
                "No gate steps are enabled. Re-run with at least one step (example: python -m sdetkit gate fast --only doctor).",
                "List available steps with: python -m sdetkit gate fast --list-steps.",
            ],
        }
        text = (
            _stable_json(empty_payload)
            if ns.format == "json" and ns.stable_json
            else json.dumps(empty_payload, sort_keys=True) + "\n"
            if ns.format == "json"
            else _format_md(empty_payload)
            if ns.format == "md"
            else _format_text(empty_payload)
        )
        _write_output(text, ns.out)
        return 2

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
    gate_payload: dict[str, Any] = {
        "profile": "fast",
        "root": str(root),
        "request_context": request_context,
        "ok": not bool(failed),
        "failed_steps": failed,
        "steps": steps,
    }
    recommendations = _fast_recommendations(steps, failed)
    if recommendations:
        gate_payload["recommendations"] = recommendations

    if ns.format == "json":
        if getattr(ns, "stable_json", False):
            rendered = _stable_json(_normalize_gate_payload(gate_payload))
        else:
            rendered = json.dumps(gate_payload, sort_keys=True) + "\n"
    elif ns.format == "md":
        rendered = _format_md(gate_payload)
    else:
        rendered = _format_text(gate_payload)

    _write_output(rendered, ns.out)

    if gate_payload["ok"]:
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
    if payload.get("recommendations"):
        lines.append("recommendations:")
        for item in payload["recommendations"]:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _release_recommendations(failed_steps: list[str]) -> list[str]:
    mapping = {
        "doctor_release": "Inspect release readiness output: python -m sdetkit doctor --release --format json --out build/doctor-release.json.",
        "playbooks_validate": "Run playbook validation directly for details: python -m sdetkit playbooks validate --recommended --format json.",
        "gate_fast": "Inspect fast gate evidence: python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json.",
        "code_scanning": (
            "Inspect security scanning output: python -m sdetkit security scan --format sarif "
            "--output build/code-scanning.sarif --fail-on high."
        ),
    }
    return [mapping[s] for s in failed_steps if s in mapping]


def _normalize_release_steps(steps: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for step in steps:
        cleaned: dict[str, Any] = dict(step)
        cleaned.pop("duration_ms", None)
        cleaned.pop("stdout", None)
        cleaned.pop("stderr", None)
        step_cmd = cleaned.get("cmd")
        if isinstance(step_cmd, list):
            cleaned["cmd"] = _normalize_release_cmd([str(t) for t in step_cmd], root)
        normalized.append(cleaned)
    return normalized


def _release_commands(ns: argparse.Namespace, root: Path) -> list[tuple[str, list[str]]]:
    code_scan_out = str(Path(getattr(ns, "code_scan_out", "build/code-scanning.sarif")))
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

    return [
        ("doctor_release", doctor_cmd),
        (
            "code_scanning",
            [
                sys.executable,
                "-m",
                "sdetkit",
                "security",
                "scan",
                "--root",
                str(root),
                "--format",
                "sarif",
                "--output",
                code_scan_out,
                "--fail-on",
                "high",
                *(["--include-info"] if getattr(ns, "code_scan_include_info", False) else []),
            ],
        ),
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


def _run_release(ns: argparse.Namespace) -> int:
    root = Path(ns.root).resolve()
    try:
        request_context = _request_context(ns)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    commands = _release_commands(ns, root)
    if not commands:
        payload: dict[str, Any] = {
            "profile": "release",
            "root": "<repo>",
            "request_context": request_context,
            "dry_run": bool(ns.dry_run),
            "ok": False,
            "failed_steps": ["configuration"],
            "steps": [],
            "recommendations": [
                "No release checks are enabled. Re-run with default options: python -m sdetkit gate release.",
                "Inspect available release checks by running: python -m sdetkit gate release --dry-run --format json.",
            ],
        }
        rendered = (
            json.dumps(payload, sort_keys=True) + "\n"
            if ns.format == "json"
            else _format_release_text(payload)
        )
        _write_output(rendered, ns.out)
        return 2

    steps: list[dict[str, Any]] = []
    for step_id, cmd in commands:
        if ns.dry_run:
            steps.append({"id": step_id, "cmd": cmd, "dry_run": True, "rc": None, "ok": True})
        else:
            steps.append({"id": step_id, **_run(cmd, cwd=root)})

    failed = [s["id"] for s in steps if not s.get("ok", False)]
    steps = _normalize_release_steps(steps, root)

    payload = {
        "profile": "release",
        "root": "<repo>",
        "request_context": request_context,
        "dry_run": bool(ns.dry_run),
        "ok": not bool(failed),
        "failed_steps": failed,
        "steps": steps,
        "ai_assistance": {
            "recommended_review_command": (
                "python -m sdetkit review . --format operator-json "
                f"--work-id {request_context['work_id'] or '<work-id>'} "
                f"--code-scan-json {Path(getattr(ns, 'code_scan_out', 'build/code-scanning.sarif')).as_posix()}"
            ),
            "adoption_focus": "doctor + gate + review adaptive alignment for every PR",
        },
    }
    recommendations = _release_recommendations(failed)
    if recommendations:
        payload["recommendations"] = recommendations

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
        bp.add_argument("--profile", choices=["fast", "release"], default="fast")
        ns, extra = bp.parse_known_args(args0[1:])
        if extra and extra[0] == "--":
            extra = extra[1:]

        root = Path.cwd()
        snap = (
            Path(ns.path)
            if isinstance(ns.path, str) and ns.path
            else _baseline_snapshot_path(root, ns.profile)
        )
        if not snap.is_absolute():
            snap = root / snap
        snap.parent.mkdir(parents=True, exist_ok=True)

        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc_fast = main([ns.profile, "--format", "json"] + list(extra))
        cur_text = buf.getvalue()
        if rc_fast != 0:
            return rc_fast

        try:
            cur_obj = json.loads(cur_text)
        except Exception:
            cur_obj = None

        if isinstance(cur_obj, dict):
            norm = _normalize_gate_payload(cur_obj) if ns.profile == "fast" else cur_obj
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
    fast.add_argument("--stable-json", action="store_true")
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
    release.add_argument("--work-id", default="")
    release.add_argument("--work-context", action="append", default=[])
    release.add_argument("--code-scan-out", default="build/code-scanning.sarif")
    release.add_argument("--code-scan-include-info", action="store_true")

    fast.add_argument("--work-id", default="")
    fast.add_argument("--work-context", action="append", default=[])

    trend = sub.add_parser("trend")
    trend.add_argument("--baseline", required=True, help="Baseline gate JSON artifact path.")
    trend.add_argument("--current", required=True, help="Current gate JSON artifact path.")
    trend.add_argument("--format", choices=["text", "json"], default="text")
    trend.add_argument("--out", "--output", default=None)

    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.cmd == "fast":
        return _run_fast(ns)
    if ns.cmd == "release":
        return _run_release(ns)
    if ns.cmd == "trend":
        return _run_trend(ns)

    sys.stderr.write("unknown gate command\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
