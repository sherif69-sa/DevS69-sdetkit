from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _run_text(args: Sequence[str], *, cwd: Path) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd),
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        return 127, str(exc)
    output = completed.stdout.strip() or completed.stderr.strip()
    return completed.returncode, output


def _git_value(repo: Path, args: Sequence[str], fallback: str) -> str:
    rc, output = _run_text(["git", *args], cwd=repo)
    if rc != 0 or not output:
        return fallback
    return output.splitlines()[0].strip() or fallback


def _git_dirty(repo: Path) -> bool:
    rc, output = _run_text(["git", "status", "--short"], cwd=repo)
    return rc == 0 and bool(output.strip())


def _command_steps() -> list[dict[str, Any]]:
    return [
        {
            "id": "gate_fast",
            "label": "Fast release confidence gate",
            "command": "python -m sdetkit gate fast",
            "status": "ready",
            "tier": "public_stable",
            "executable": True,
        },
        {
            "id": "gate_release",
            "label": "Strict release confidence gate",
            "command": "python -m sdetkit gate release",
            "status": "ready",
            "tier": "public_stable",
            "executable": True,
        },
        {
            "id": "doctor",
            "label": "Repository and release-readiness diagnostics",
            "command": "python -m sdetkit doctor",
            "status": "ready",
            "tier": "public_stable",
            "executable": True,
        },
        {
            "id": "review",
            "label": "Operator review workflow",
            "command": "python -m sdetkit review . --profile release --format operator-json",
            "status": "ready",
            "tier": "public_stable",
            "executable": False,
        },
        {
            "id": "readiness",
            "label": "Production readiness scorecard",
            "command": "python -m sdetkit readiness",
            "status": "ready",
            "tier": "public_stable",
            "executable": True,
        },
        {
            "id": "release_room",
            "label": "Release-room plan",
            "command": "python -m sdetkit release-room",
            "status": "planned",
            "tier": "future_public_surface",
            "executable": False,
        },
    ]


def _execution_args(step_id: str) -> list[str]:
    commands = {
        "gate_fast": [sys.executable, "-m", "sdetkit", "gate", "fast"],
        "gate_release": [sys.executable, "-m", "sdetkit", "gate", "release"],
        "doctor": [sys.executable, "-m", "sdetkit", "doctor"],
        "readiness": [sys.executable, "-m", "sdetkit", "readiness"],
    }
    return commands[step_id]


def _selected_execute_ids(*, include_release: bool) -> set[str]:
    selected = {"gate_fast", "doctor", "readiness"}
    if include_release:
        selected.add("gate_release")
    return selected


def _run_step_process(
    args: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int,
) -> tuple[int, str, str, int]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd),
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return completed.returncode, completed.stdout, completed.stderr, elapsed_ms
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr = stderr or f"timed out after {timeout_seconds}s"
        return 124, stdout, stderr, elapsed_ms
    except OSError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return 127, "", str(exc), elapsed_ms


def _write_step_outputs(
    *,
    out_dir: Path,
    step_id: str,
    stdout: str,
    stderr: str,
) -> tuple[Path, Path]:
    step_dir = out_dir / "steps"
    step_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = step_dir / f"{step_id}.stdout"
    stderr_path = step_dir / f"{step_id}.stderr"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    return stdout_path, stderr_path


def _execute_steps(
    *,
    steps: list[dict[str, Any]],
    repo: Path,
    out_dir: Path,
    include_release: bool,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    selected = _selected_execute_ids(include_release=include_release)
    executed_steps = []

    for step in steps:
        updated = dict(step)
        step_id = str(step["id"])

        if step_id not in selected:
            updated["executed"] = False
            executed_steps.append(updated)
            continue

        args = _execution_args(step_id)
        rc, stdout, stderr, elapsed_ms = _run_step_process(
            args,
            cwd=repo,
            timeout_seconds=timeout_seconds,
        )
        stdout_path, stderr_path = _write_step_outputs(
            out_dir=out_dir,
            step_id=step_id,
            stdout=stdout,
            stderr=stderr,
        )

        updated["executed"] = True
        updated["status"] = "passed" if rc == 0 else "failed"
        updated["rc"] = rc
        updated["elapsed_ms"] = elapsed_ms
        updated["stdout_path"] = stdout_path.resolve().as_posix()
        updated["stderr_path"] = stderr_path.resolve().as_posix()
        executed_steps.append(updated)

    return executed_steps


def _artifact(path: Path, label: str, kind: str) -> dict[str, str]:
    return {
        "label": label,
        "kind": kind,
        "path": path.as_posix(),
    }


def _step_artifacts(steps: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    artifacts = []
    for step in steps:
        step_id = str(step["id"])
        stdout_path = step.get("stdout_path")
        stderr_path = step.get("stderr_path")
        if isinstance(stdout_path, str):
            artifacts.append(
                {
                    "label": f"{step_id} stdout",
                    "kind": "stdout",
                    "path": stdout_path,
                }
            )
        if isinstance(stderr_path, str):
            artifacts.append(
                {
                    "label": f"{step_id} stderr",
                    "kind": "stderr",
                    "path": stderr_path,
                }
            )
    return artifacts


def _execution_counts(steps: Sequence[dict[str, Any]]) -> tuple[int, int, int]:
    executed = [step for step in steps if step.get("executed") is True]
    passed = [step for step in executed if step.get("status") == "passed"]
    failed = [step for step in executed if step.get("status") == "failed"]
    return len(executed), len(passed), len(failed)


def _execution_findings(steps: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    findings = []
    for step in steps:
        if step.get("executed") is True and step.get("status") == "failed":
            findings.append(
                {
                    "severity": "error",
                    "code": "STEP_FAILED",
                    "message": f"{step['id']} failed with rc={step.get('rc')}.",
                }
            )
    return findings


def build_bundle(
    repo: Path,
    out_dir: Path,
    *,
    execute: bool = False,
    include_release: bool = False,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    repo = repo.resolve()
    out_dir = out_dir.resolve()
    generated_at = _utc_now()
    branch = _git_value(repo, ["branch", "--show-current"], "unknown")
    commit = _git_value(repo, ["rev-parse", "HEAD"], "unknown")
    dirty = _git_dirty(repo)

    steps = _command_steps()
    if execute:
        steps = _execute_steps(
            steps=steps,
            repo=repo,
            out_dir=out_dir,
            include_release=include_release,
            timeout_seconds=timeout_seconds,
        )
    else:
        steps = [dict(step, executed=False) for step in steps]

    executed_count, passed_count, failed_count = _execution_counts(steps)

    findings = _execution_findings(steps)
    if dirty:
        findings.append(
            {
                "severity": "warning",
                "code": "WORKTREE_DIRTY",
                "message": "Working tree has uncommitted changes.",
            }
        )

    next_actions = [
        {
            "id": "run_fast_gate",
            "command": "python -m sdetkit gate fast",
            "reason": "Check fast release-confidence feedback first.",
        },
        {
            "id": "run_release_gate",
            "command": "python -m sdetkit gate release",
            "reason": "Run strict release gate before operator signoff.",
        },
        {
            "id": "run_doctor",
            "command": "python -m sdetkit doctor",
            "reason": "Collect deterministic repository diagnostics.",
        },
    ]

    if failed_count:
        decision = "NO_SHIP"
        risk_band = "high"
    elif findings:
        decision = "SHIP_WITH_FINDINGS"
        risk_band = "medium"
    else:
        decision = "SHIP"
        risk_band = "low"

    artifacts = [
        _artifact(out_dir / "mission-control.json", "Mission Control JSON bundle", "json"),
        _artifact(out_dir / "mission-control.md", "Mission Control operator brief", "markdown"),
    ]
    artifacts.extend(_step_artifacts(steps))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "ok": failed_count == 0,
        "mode": "execute" if execute else "plan",
        "decision": decision,
        "risk_band": risk_band,
        "repo": {
            "path": repo.as_posix(),
            "branch": branch,
            "commit": commit,
            "dirty": dirty,
        },
        "executed_step_count": executed_count,
        "passed_step_count": passed_count,
        "failed_step_count": failed_count,
        "steps": steps,
        "findings": findings,
        "artifacts": artifacts,
        "next_actions": next_actions,
    }


def render_markdown(bundle: dict[str, Any]) -> str:
    repo = bundle["repo"]
    lines = [
        "# Mission Control",
        "",
        f"Generated: {bundle['generated_at_utc']}",
        f"Mode: {bundle['mode']}",
        f"Decision: {bundle['decision']}",
        f"Risk band: {bundle['risk_band']}",
        f"Repository: {repo['path']}",
        f"Branch: {repo['branch']}",
        f"Commit: {repo['commit']}",
        f"Dirty: {str(repo['dirty']).lower()}",
        f"Executed steps: {bundle['executed_step_count']}",
        f"Passed steps: {bundle['passed_step_count']}",
        f"Failed steps: {bundle['failed_step_count']}",
        "",
        "## Steps",
        "",
    ]

    for step in bundle["steps"]:
        line = f"- {step['id']}: {step['status']} - `{step['command']}`"
        if step.get("executed") is True:
            line += f" rc={step.get('rc')} elapsed_ms={step.get('elapsed_ms')}"
        lines.append(line)

    lines.extend(["", "## Findings", ""])

    if bundle["findings"]:
        for finding in bundle["findings"]:
            lines.append(f"- {finding['severity']}: {finding['code']} - {finding['message']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Next actions", ""])

    for action in bundle["next_actions"]:
        lines.append(f"- {action['id']}: `{action['command']}`")

    lines.append("")
    return "\n".join(lines)


def write_bundle(bundle: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "mission-control.json"
    md_path = out_dir / "mission-control.md"
    json_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(bundle), encoding="utf-8")
    return json_path, md_path


def _run(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    out_dir = Path(args.out_dir)
    bundle = build_bundle(
        repo,
        out_dir,
        execute=bool(args.execute),
        include_release=bool(args.include_release),
        timeout_seconds=int(args.timeout_seconds),
    )
    json_path, md_path = write_bundle(bundle, out_dir)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(f"decision={bundle['decision']} risk_band={bundle['risk_band']}")
    return 0 if bundle["ok"] else 2


def _summarize(args: argparse.Namespace) -> int:
    path = Path(args.bundle)
    bundle = json.loads(path.read_text(encoding="utf-8"))
    print(f"decision={bundle['decision']}")
    print(f"risk_band={bundle['risk_band']}")
    print(f"repo={bundle['repo']['path']}")
    print(f"mode={bundle.get('mode', 'plan')}")
    print(f"steps={len(bundle['steps'])}")
    print(f"executed_steps={bundle.get('executed_step_count', 0)}")
    print(f"failed_steps={bundle.get('failed_step_count', 0)}")
    print(f"findings={len(bundle['findings'])}")
    return 0


def _schema(_: argparse.Namespace) -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "required_top_level_keys": [
            "schema_version",
            "generated_at_utc",
            "ok",
            "mode",
            "decision",
            "risk_band",
            "repo",
            "executed_step_count",
            "passed_step_count",
            "failed_step_count",
            "steps",
            "findings",
            "artifacts",
            "next_actions",
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit mission-control",
        description="Create a deterministic release-confidence evidence bundle.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Write mission-control.json and mission-control.md")
    run.add_argument("--repo", default=".")
    run.add_argument("--out-dir", default="build/mission-control")
    run.add_argument("--execute", action="store_true")
    run.add_argument("--include-release", action="store_true")
    run.add_argument("--timeout-seconds", type=int, default=60)
    run.set_defaults(func=_run)

    summarize = sub.add_parser("summarize", help="Summarize a mission-control.json bundle")
    summarize.add_argument("--bundle", required=True)
    summarize.set_defaults(func=_summarize)

    schema = sub.add_parser("schema", help="Print the Mission Control bundle schema summary")
    schema.set_defaults(func=_schema)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
