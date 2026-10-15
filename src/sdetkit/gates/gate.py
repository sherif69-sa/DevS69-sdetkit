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

from ..failure_vector_adapters import extract_ecosystem_failure_vector
from ..repo_model import build_repo_model
from ..utils.bools import coerce_bool
from ..verdict import build_verdict, combine_verdicts, git_provenance, verdict_from_artifact
from .gate_config import load_gate_config, plan_mypy, plan_pytest, plan_ruff, plan_suite
from .latest_run import record_latest_run
from .project_env import (
    ProjectPython,
    checkout_problem,
    mypy_environment_problem,
    pytest_environment_problem,
    resolve_project_python,
    setup_command,
)

AVAILABLE_STEPS = [
    "ruff_fix",
    "ruff_format_apply",
    "doctor",
    "ci_templates",
    "ruff",
    "ruff_format",
    "mypy",
    "pytest",
    "tests",
]


def _normalize_gate_payload(payload: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = dict(payload)
    root = out.get("root")
    root_str = root if isinstance(root, str) else ""
    out["root"] = "<repo>"
    out.pop("environment", None)
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


def _run_chain(commands: list[list[str]], cwd: Path) -> dict[str, Any]:
    """Run a workspace's configure/build/test commands in order, stopping at the first failure."""

    started = time.time()
    chain: list[dict[str, Any]] = []
    result: dict[str, Any] = {"cmd": [], "rc": 0, "ok": True, "stdout": "", "stderr": ""}
    for cmd in commands:
        result = _run(cmd, cwd=cwd)
        chain.append({"cmd": result.get("cmd", cmd), "rc": result.get("rc")})
        if not result.get("ok"):
            break
    # stdout/stderr belong to the last command run, so a failure is diagnosed
    # from the command that failed rather than from earlier configure output.
    return {
        **result,
        "ok": bool(result.get("ok", True)),
        "duration_ms": int((time.time() - started) * 1000),
        "chain": chain,
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


def _nested_next_action(step: dict[str, Any] | None) -> dict[str, str] | None:
    """Return the ``next_action`` card a failing sdetkit sub-step already computed.

    Steps such as ``doctor`` emit JSON with their own diagnosis; re-parsing that
    JSON as a log would surface the whole document as the "first failure".
    """

    if not isinstance(step, dict):
        return None
    try:
        data = json.loads(str(step.get("stdout", "") or ""))
    except (TypeError, ValueError):
        return None
    card = data.get("next_action") if isinstance(data, dict) else None
    if not isinstance(card, dict):
        return None
    return {key: str(card.get(key, "") or "") for key in _NEXT_ACTION_KEYS}


_NEXT_ACTION_KEYS = ("classification", "first_failure", "affected_file", "next_command")


def _next_action_card(payload: dict[str, Any]) -> dict[str, str]:
    profile = str(payload.get("profile", "fast") or "fast")
    ok = coerce_bool(payload.get("ok"), default=False)
    failed_steps = [str(step) for step in (payload.get("failed_steps") or [])]
    recommendations = [
        str(item) for item in (payload.get("recommendations") or []) if str(item).strip()
    ]
    if ok and not failed_steps:
        next_command = (
            "python -m sdetkit gate release --format json --out build/release-preflight.json"
            if profile == "fast"
            else "python -m sdetkit doctor --format json --out build/doctor.json"
        )
        return {
            "decision": "CONTINUE",
            "classification": "",
            "first_failure": "",
            "affected_file": "",
            "next_command": next_command,
            "authority": "review-first",
        }

    steps = payload.get("steps")
    by_id = {
        str(step.get("id", "")): step
        for step in (steps if isinstance(steps, list) else [])
        if isinstance(step, dict)
    }
    # A code failure outranks a check that could not run against this repository.
    code_failures = [s for s in failed_steps if not by_id.get(s, {}).get("environment_problem")]
    first_step_id = (code_failures or failed_steps or ["unknown"])[0]
    first_step = by_id.get(first_step_id)
    log_text = ""
    if isinstance(first_step, dict):
        log_text = f"{first_step.get('stdout', '')}\n{first_step.get('stderr', '')}"

    classification = "unknown"
    first_failure = first_step_id
    affected_file = ""
    next_command = (
        recommendations[0]
        if recommendations
        else (
            f"python -m sdetkit gate {profile} --format json"
            if profile in {"fast", "release"}
            else "python -m sdetkit doctor --format json --out build/doctor.json"
        )
    )
    if isinstance(first_step, dict) and first_step.get("environment_problem"):
        return {
            "decision": "NOT_RUN",
            "classification": "environment",
            "first_failure": str(first_step["environment_problem"]),
            "affected_file": "",
            "next_command": str(first_step.get("next_command") or next_command),
            "authority": "review-first",
        }
    nested = _nested_next_action(first_step)
    if nested is not None:
        return {
            "decision": "NO-SHIP",
            "classification": nested.get("classification") or first_step_id,
            "first_failure": nested.get("first_failure") or first_step_id,
            "affected_file": nested.get("affected_file", ""),
            "next_command": nested.get("next_command") or next_command,
            "authority": "review-first",
        }
    if log_text.strip():
        vector = extract_ecosystem_failure_vector(log_text, check=first_step_id).vector
        classification = vector.failure_class or "unknown"
        first_failure = vector.actual_failure or vector.first_failing_line or first_step_id
        affected_file = vector.affected_files[0] if vector.affected_files else ""
        if vector.local_repro_command:
            next_command = vector.local_repro_command
    return {
        "decision": "NO-SHIP",
        "classification": classification,
        "first_failure": first_failure,
        "affected_file": affected_file,
        "next_command": next_command,
        "authority": "review-first",
    }


def _attach_next_action(payload: dict[str, Any]) -> dict[str, Any]:
    payload["next_action"] = _next_action_card(payload)
    return payload


def _attach_verdict(payload: dict[str, Any], *, source: str, root: Path) -> dict[str, Any]:
    card = payload.get("next_action") or {}
    payload["provenance"] = git_provenance(root)
    failed = [str(step) for step in payload.get("failed_steps", [])]
    problems = {
        str(step.get("id")): str(step["environment_problem"])
        for step in payload.get("steps", [])
        if isinstance(step, dict) and step.get("environment_problem")
    }
    if failed and all(step in problems for step in failed):
        # Nothing failed in the code: the checks could not run against this repository.
        payload["verdict"] = build_verdict(
            source=source,
            decision="NOT_RUN",
            reasons=[
                f"{step} did not run against this repository: {problems[step]}" for step in failed
            ],
            next_action=str(card.get("next_command") or ""),
        )
        return payload
    payload["verdict"] = build_verdict(
        source=source,
        decision="NO-SHIP" if failed else (card.get("decision") or "CONTINUE"),
        reasons=[f"step failed: {step}" for step in failed],
        next_action=str(card.get("next_command") or ""),
    )
    return payload


def _format_next_action_text(payload: dict[str, Any]) -> list[str]:
    card = payload.get("next_action")
    if not isinstance(card, dict):
        return []
    lines = ["next_action:"]
    for key in (
        "decision",
        "classification",
        "first_failure",
        "affected_file",
        "next_command",
        "authority",
    ):
        lines.append(f"{key}: {card.get(key, '')}")
    return lines


def _format_text(payload: dict[str, Any]) -> str:
    ok = coerce_bool(payload.get("ok"), default=False)
    lines: list[str] = []
    lines.append(f"gate fast: {'OK' if ok else 'FAIL'}")
    environment = payload.get("environment")
    if isinstance(environment, dict):
        lines.append(f"python: {environment.get('python', '')} ({environment.get('source', '')})")
    for step in payload.get("steps", []):
        marker = "OK" if step.get("ok") else "FAIL"
        dur = step.get("duration_ms", 0)
        step_id = step.get("id", "unknown")
        lines.append(f"[{marker}] {step_id} ({dur}ms) rc={step.get('rc')}")
    for skipped in payload.get("skipped_steps", []):
        lines.append(f"[SKIP] {skipped.get('id', 'unknown')}: {skipped.get('reason', '')}")
    if payload.get("failed_steps"):
        lines.append("failed_steps:")
        for s in payload["failed_steps"]:
            lines.append(f"- {s}")
    if payload.get("recommendations"):
        lines.append("recommendations:")
        for item in payload["recommendations"]:
            lines.append(f"- {item}")
    lines.extend(_format_next_action_text(payload))
    return "\n".join(lines) + "\n"


_MD_DECISIONS = {
    "SHIP": (":white_check_mark:", "Every check ran against this repository and passed."),
    "REVIEW": (":eyes:", "Nothing blocks, but a person should look first."),
    "NOT_RUN": (
        ":white_circle:",
        "The checks could not run against this repository, so nothing was proven either way.",
    ),
    "NO_SHIP": (":x:", "A check failed."),
}


def _md_code(text: object) -> str:
    """Inline code that survives backticks and table pipes in the text."""

    value = " ".join(str(text).split()).replace("|", "\\|")
    fence = "``" if "`" in value else "`"
    return f"{fence}{value}{fence}" if value else ""


def _md_seconds(step: dict[str, Any]) -> str:
    try:
        return f"{float(step.get('duration_ms') or 0) / 1000:.1f}s"
    except (TypeError, ValueError):
        return ""


def _format_md(payload: dict[str, Any]) -> str:
    """The verdict first, then each step, the first failure and the command to run next.

    This is the GitHub job summary and pull request comment of the SDETKit gate action
    (`gate fast --summary-out`), so it names no machine-specific paths except the
    interpreter that ran the checks.
    """

    ok = coerce_bool(payload.get("ok"), default=False)
    raw_verdict = payload.get("verdict")
    verdict: dict[str, Any] = raw_verdict if isinstance(raw_verdict, dict) else {}
    decision = str(verdict.get("decision") or ("SHIP" if ok else "NO_SHIP"))
    icon, meaning = _MD_DECISIONS.get(decision, (":grey_question:", ""))
    lines = [f"### {icon} SDETKit gate fast: {decision}", ""]
    if meaning:
        lines += [meaning, ""]

    rows: list[str] = []
    for step in payload.get("steps", []):
        if step.get("ok"):
            result = ":white_check_mark: passed"
        elif step.get("environment_problem"):
            result = ":white_circle: not run (environment)"
        else:
            result = f":x: failed (exit {step.get('rc')})"
        rows.append(f"| {_md_code(step.get('id', 'unknown'))} | {result} | {_md_seconds(step)} |")
    recorded = {step.get("id") for step in payload.get("steps", [])}
    for step_id in payload.get("failed_steps", []):
        if step_id not in recorded:  # a failure with no step record, such as "configuration"
            rows.append(f"| {_md_code(step_id)} | :x: failed | |")
    for skipped in payload.get("skipped_steps", []):
        reason = str(skipped.get("reason", "")).replace("|", "\\|")
        rows.append(f"| {_md_code(skipped.get('id', 'unknown'))} | skipped: {reason} | |")
    if rows:
        lines += ["| Step | Result | Time |", "| --- | --- | --- |", *rows, ""]

    raw_card = payload.get("next_action")
    card: dict[str, Any] = raw_card if isinstance(raw_card, dict) else {}
    if card.get("first_failure"):
        where = f" in {_md_code(card['affected_file'])}" if card.get("affected_file") else ""
        kind = f" ({card['classification']})" if card.get("classification") else ""
        lines += [f"**First failure{kind}:** {_md_code(card['first_failure'])}{where}", ""]
    reasons = [str(reason) for reason in verdict.get("reasons") or [] if reason]
    if reasons:
        lines += ["**Why:**", *[f"- {reason}" for reason in reasons], ""]
    next_command = card.get("next_command") or verdict.get("next_action")
    if next_command:
        lines += [f"**Next:** {_md_code(next_command)}", ""]
    for item in payload.get("recommendations", []):
        if item and item != next_command:
            lines.append(f"- {item}")
    if payload.get("recommendations"):
        lines.append("")

    environment = payload.get("environment")
    if isinstance(environment, dict) and environment.get("python"):
        lines.append(
            f"Checks ran with {_md_code(environment['python'])} ({environment.get('source', '')})."
            " Nothing was applied, merged or dismissed."
        )
    else:
        lines.append("Nothing was applied, merged or dismissed.")
    return "\n".join(lines) + "\n"


def _append_summary(text: str, path: str | None) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(text)


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
        if step.get("environment_problem"):
            recommendations.append(str(step.get("next_command") or ""))
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
        if step_id.startswith("tests:"):
            command = shlex.join(str(token) for token in step.get("cmd") or [])
            workdir = str(step.get("working_directory") or ".")
            recommendations.append(command if workdir == "." else f"cd {workdir} && {command}")
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


def _environment_step(
    step_id: str, cmd: list[str], problem: str, next_command: str
) -> dict[str, Any]:
    """A step that could not run against this repository, kept as a failure that names why."""

    return {
        "id": step_id,
        "cmd": cmd,
        "rc": None,
        "ok": False,
        "duration_ms": 0,
        "stdout": "",
        "stderr": problem,
        "environment_problem": problem,
        "next_command": next_command,
    }


def _mark_environment_problem(step: dict[str, Any], problem: str | None, next_command: str) -> None:
    if problem and not step.get("ok"):
        step["environment_problem"] = problem
        step["next_command"] = next_command


def _mark_checkout_problem(
    steps: list[dict[str, Any]], root: Path, env: ProjectPython, next_command: str
) -> None:
    """A failing mypy or pytest run says nothing about this checkout when it never saw it."""

    failing = [
        step
        for step in steps
        if step.get("id") in {"mypy", "pytest"}
        and not step.get("ok")
        and not step.get("environment_problem")
    ]
    if not failing:
        return
    problem = checkout_problem(root, env)
    if problem is None:
        return
    for step in failing:
        # mypy reads the checkout's files; only missing dependencies break it.
        if step["id"] == "pytest" or not problem.installed:
            _mark_environment_problem(step, problem.reason, next_command)


def _mypy_command(env: ProjectPython, args: tuple[str, ...]) -> list[str]:
    cmd = [*env.runner("mypy"), *args]
    if cmd[0] != env.executable and not any(a.startswith("--python-executable") for a in args):
        # SDETKit's mypy checks the project's code against the project's installed packages.
        cmd.append(f"--python-executable={env.executable}")
    return cmd


def _run_fast(ns: argparse.Namespace) -> int:
    root = Path(ns.root).resolve()
    only = _parse_step_filter(ns.only)
    skip = _parse_step_filter(ns.skip)
    gate_profile = str(getattr(ns, "profile", "strict") or "strict")

    # External adoption must prove SDETKit can install, run, and emit evidence
    # before enforcing repo-specific quality policy. Keep strict as the default.
    if gate_profile == "adoption" and not only:
        ns.no_ci_templates = True
        ns.no_ruff = True
        ns.no_mypy = True
        ns.no_pytest = True
        ns.no_tests = True

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

    config = load_gate_config(root)
    if config.errors:
        sys.stderr.write("gate: " + "; ".join(config.errors) + "\n")
        return 2
    model = build_repo_model(root)
    try:
        env = resolve_project_python(root, getattr(ns, "python", None))
    except ValueError as exc:
        sys.stderr.write(f"gate: {exc}\n")
        return 2
    setup_then_rerun = f"{setup_command(root)} && python -m sdetkit gate fast"
    skipped_steps: list[dict[str, str]] = []

    def record_skip(step_id: str, reason: str) -> None:
        skipped_steps.append({"id": step_id, "reason": reason})

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
        _attach_next_action(empty_payload)
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
        _append_summary(_format_md(empty_payload), getattr(ns, "summary_out", None))
        return 2

    steps: list[dict[str, Any]] = []

    if (ns.fix or ns.fix_only) and should_run("ruff_fix"):
        steps.append(
            {
                "id": "ruff_fix",
                **_run([*env.runner("ruff"), "check", "--fix", "."], cwd=root),
            }
        )
    if (ns.fix or ns.fix_only) and should_run("ruff_format_apply"):
        steps.append(
            {
                "id": "ruff_format_apply",
                **_run([*env.runner("ruff"), "format", "."], cwd=root),
            }
        )
        if ns.fix_only:
            ns.no_doctor = True
            ns.no_ci_templates = True
            ns.no_ruff = True
            ns.no_mypy = True
            ns.no_pytest = True
            ns.no_tests = True

    if not ns.no_doctor and should_run("doctor"):
        if gate_profile == "adoption":
            doctor_cmd = [
                sys.executable,
                "-m",
                "sdetkit",
                "doctor",
                "--format",
                "json",
            ]
        else:
            fail_on = "medium" if ns.strict else "high"
            doctor_cmd = [
                sys.executable,
                "-m",
                "sdetkit",
                "doctor",
                *config.doctor_args,
                "--fail-on",
                fail_on,
                "--format",
                "json",
            ]
        steps.append({"id": "doctor", **_run(doctor_cmd, cwd=root)})

    ci_templates_requested = config.ci_templates or "ci_templates" in only
    if not ns.no_ci_templates and should_run("ci_templates") and not ci_templates_requested:
        record_skip("ci_templates", "not enabled ([tool.sdetkit.gate] ci_templates = true)")
    elif not ns.no_ci_templates and should_run("ci_templates"):
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

    for ruff_step, ruff_cmd in (("ruff", ["check"]), ("ruff_format", ["format", "--check"])):
        if ns.no_ruff or not should_run(ruff_step):
            continue
        ruff_plan = plan_ruff(
            root, config, force=bool({"ruff", "ruff_format"} & only), command=ruff_cmd[0]
        )
        if ruff_plan.skipped:
            record_skip(ruff_step, ruff_plan.skip_reason)
            continue
        ruff_result = {
            "id": ruff_step,
            **_run([*env.runner("ruff"), *ruff_cmd, *ruff_plan.args], cwd=root),
        }
        if ruff_plan.source:
            ruff_result["targets_from"] = ruff_plan.source
        steps.append(ruff_result)

    if not ns.no_mypy and should_run("mypy"):
        mypy_plan = plan_mypy(root, config, ns.mypy_args, force="mypy" in only)
        if mypy_plan.skipped:
            record_skip("mypy", mypy_plan.skip_reason)
        else:
            if mypy_plan.more:
                commands = [_mypy_command(env, args) for args in (mypy_plan.args, *mypy_plan.more)]
                mypy_step = {"id": "mypy", **_run_chain(commands, cwd=root)}
            else:
                mypy_step = {"id": "mypy", **_run(_mypy_command(env, mypy_plan.args), cwd=root)}
            if mypy_plan.source:
                mypy_step["targets_from"] = mypy_plan.source
            if env.is_sdetkit:
                mypy_output = f"{mypy_step.get('stdout', '')}\n{mypy_step.get('stderr', '')}"
                _mark_environment_problem(
                    mypy_step, mypy_environment_problem(mypy_output, root), setup_then_rerun
                )
            steps.append(mypy_step)

    if not ns.no_pytest and should_run("pytest"):
        pytest_plan = plan_pytest(
            root, config, ns.pytest_args, ns.full_pytest, force="pytest" in only, model=model
        )
        pytest_cmd = [env.executable, "-m", "pytest", *pytest_plan.args]
        if pytest_plan.skipped:
            record_skip("pytest", pytest_plan.skip_reason)
        elif "pytest" not in env.tools and not env.is_sdetkit:
            steps.append(
                _environment_step(
                    "pytest",
                    pytest_cmd,
                    f"pytest is not installed in the project environment ({env.executable})",
                    setup_then_rerun,
                )
            )
        else:
            pytest_step = {"id": "pytest", **_run(pytest_cmd, cwd=root)}
            pytest_output = f"{pytest_step.get('stdout', '')}\n{pytest_step.get('stderr', '')}"
            _mark_environment_problem(
                pytest_step, pytest_environment_problem(pytest_output, root, env), setup_then_rerun
            )
            steps.append(pytest_step)

    _mark_checkout_problem(steps, root, env, setup_then_rerun)

    unrunnable: list[dict[str, str]] = []
    if not getattr(ns, "no_tests", False) and should_run("tests"):
        for suite in model.non_python_suites():
            suite_plan = plan_suite(root, suite)
            if suite_plan.skipped:
                record_skip(suite.step_id, suite_plan.skip_reason)
                unrunnable.append({"id": suite.step_id, "reason": suite_plan.skip_reason})
                continue
            steps.append(
                {
                    "id": suite.step_id,
                    "working_directory": suite.working_directory,
                    **_run_chain(suite.argv(), cwd=root / suite.working_directory),
                }
            )

    failed = [s["id"] for s in steps if not s.get("ok", False)]
    gate_payload: dict[str, Any] = {
        "profile": "fast",
        "gate_profile": gate_profile,
        "root": str(root),
        "request_context": request_context,
        "repo": {
            "languages": list(model.languages),
            "ci_systems": list(model.ci_systems),
            "test_suites": [suite.step_id for suite in model.test_suites],
        },
        "ok": not bool(failed),
        "failed_steps": failed,
        "steps": steps,
        "environment": env.as_dict(),
    }
    if skipped_steps:
        gate_payload["skipped_steps"] = skipped_steps
    recommendations = _fast_recommendations(steps, failed)
    if recommendations:
        gate_payload["recommendations"] = recommendations
    _attach_next_action(gate_payload)
    _attach_verdict(gate_payload, source="gate fast", root=root)
    if unrunnable and gate_payload["ok"]:
        # Green steps do not prove a release when the repository's own tests never ran.
        gate_payload["verdict"] = build_verdict(
            source="gate fast",
            decision="NOT_RUN",
            reasons=[f"{item['id']} did not run: {item['reason']}" for item in unrunnable],
            next_action="Install the missing tools and re-run: python -m sdetkit gate fast",
        )

    if ns.format == "json":
        if getattr(ns, "stable_json", False):
            rendered = _stable_json(_normalize_gate_payload(gate_payload))
        else:
            rendered = json.dumps(gate_payload, sort_keys=True) + "\n"
    elif ns.format == "md":
        rendered = _format_md(gate_payload)
    else:
        rendered = _format_text(gate_payload)

    record_latest_run(root, gate_payload)
    _write_output(rendered, ns.out)
    _append_summary(_format_md(gate_payload), getattr(ns, "summary_out", None))

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
    lines.extend(_format_next_action_text(payload))
    return "\n".join(lines) + "\n"


def _release_recommendations(failed_steps: list[str]) -> list[str]:
    mapping = {
        "doctor_release": "Inspect release readiness output: python -m sdetkit doctor --release --format json --out build/doctor-release.json.",
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
    gate_profile = str(getattr(ns, "profile", "strict") or "strict")
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

    if gate_profile == "adoption":
        return [
            (
                "doctor_release",
                [sys.executable, "-m", "sdetkit", "doctor", "--format", "json"],
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
                    "--profile",
                    "adoption",
                    "--format",
                    "json",
                ],
            ),
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


def _reused_fast_step(path: Path, root: Path) -> tuple[dict[str, Any] | None, str]:
    """Reuse an earlier `gate fast` result only when it describes this exact tree."""

    if not path.is_file():
        return None, f"{path.as_posix()} does not exist"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{path.as_posix()} is not readable JSON: {exc}"
    if not isinstance(payload, dict) or payload.get("profile") != "fast":
        return None, f"{path.as_posix()} is not a gate fast result"
    raw_provenance = payload.get("provenance")
    recorded: dict[str, Any] = raw_provenance if isinstance(raw_provenance, dict) else {}
    current = git_provenance(root)
    if not current["head_sha"] or recorded.get("head_sha") != current["head_sha"]:
        return None, "the gate fast result was recorded on a different commit"
    if not recorded.get("tree_clean") or not current["tree_clean"]:
        return None, "the working tree had uncommitted changes"
    ok = bool(payload.get("ok"))
    return {
        "ok": ok,
        "rc": 0 if ok else 2,
        "reused_from": path.as_posix(),
        "stdout": json.dumps(payload, sort_keys=True),
        "stderr": "",
    }, ""


def _step_verdict(step: dict[str, Any]) -> dict[str, Any] | None:
    try:
        data = json.loads(str(step.get("stdout") or ""))
    except (TypeError, ValueError):
        return None
    return verdict_from_artifact(data) if isinstance(data, dict) else None


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
        _attach_next_action(payload)
        rendered = (
            json.dumps(payload, sort_keys=True) + "\n"
            if ns.format == "json"
            else _format_release_text(payload)
        )
        _write_output(rendered, ns.out)
        return 2

    reuse_path = getattr(ns, "reuse_fast", None)
    steps: list[dict[str, Any]] = []
    for step_id, cmd in commands:
        if ns.dry_run:
            steps.append({"id": step_id, "cmd": cmd, "dry_run": True, "rc": None, "ok": True})
            continue
        if step_id == "gate_fast" and reuse_path:
            reused, rejection = _reused_fast_step(Path(reuse_path), root)
            if reused is not None:
                steps.append({"id": step_id, "cmd": cmd, **reused})
                continue
            steps.append({"id": step_id, **_run(cmd, cwd=root), "reuse_rejected": rejection})
            continue
        steps.append({"id": step_id, **_run(cmd, cwd=root)})

    failed = [s["id"] for s in steps if not s.get("ok", False)]
    nested_verdicts = [verdict for verdict in map(_step_verdict, steps) if verdict]
    # Diagnose from the raw step output before it is stripped for stable output.
    next_action = _next_action_card(
        {
            "profile": "release",
            "ok": not bool(failed),
            "failed_steps": failed,
            "steps": steps,
            "recommendations": _release_recommendations(failed),
        }
    )
    raw_steps = steps
    steps = _normalize_release_steps(steps, root)

    payload = {
        "profile": "release",
        "gate_profile": str(getattr(ns, "profile", "strict") or "strict"),
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
    payload["next_action"] = next_action
    _attach_verdict(payload, source="gate release", root=root)
    if any(verdict.get("decision") != "SHIP" for verdict in nested_verdicts):
        # A step that passed without proving anything (gate fast whose suites
        # could not run) must not let the release read SHIP.
        payload["verdict"] = combine_verdicts(
            "gate release", [payload["verdict"], *nested_verdicts]
        )

    rendered = (
        json.dumps(payload, sort_keys=True) + "\n"
        if ns.format == "json"
        else _format_release_text(payload)
    )
    # The saved run keeps each step's output so `diagnose run` can read the failures.
    record_latest_run(root, {**payload, "steps": raw_steps})
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
            norm.pop("provenance", None)
            norm.pop("verdict", None)
            norm.pop("repo", None)
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
    fast.add_argument(
        "--summary-out",
        metavar="PATH",
        default=None,
        help="Also append the Markdown summary to PATH (for example $GITHUB_STEP_SUMMARY).",
    )
    fast.add_argument("--profile", choices=["strict", "adoption"], default="strict")
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
    fast.add_argument(
        "--no-tests",
        action="store_true",
        help="Do not run the non-Python test suites the repository model detected.",
    )

    fast.add_argument("--pytest-args", default=None)
    fast.add_argument("--full-pytest", action="store_true")
    fast.add_argument("--mypy-args", default=None)
    fast.add_argument(
        "--python",
        default=None,
        help=(
            "Interpreter for the repository's own ruff, mypy and pytest runs "
            "(default: .venv or venv in the repository, then Poetry's or Pipenv's "
            "environment, then an activated virtualenv, then SDETKit's own interpreter)."
        ),
    )

    release = sub.add_parser("release")
    release.add_argument("--root", default=".")
    release.add_argument("--format", choices=["text", "json"], default="text")
    release.add_argument("--out", "--output", default=None)
    release.add_argument("--dry-run", action="store_true")
    release.add_argument("--profile", choices=["strict", "adoption"], default="strict")
    release.add_argument("--release-full", action="store_true")
    release.add_argument("--work-id", default="")
    release.add_argument("--work-context", action="append", default=[])
    release.add_argument("--code-scan-out", default="build/code-scanning.sarif")
    release.add_argument("--code-scan-include-info", action="store_true")
    release.add_argument(
        "--reuse-fast",
        default=None,
        metavar="GATE_FAST_JSON",
        help=(
            "Reuse this `gate fast --format json` result instead of running gate fast again, "
            "when it was recorded on the current commit with a clean tree"
        ),
    )

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
