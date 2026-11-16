"""`sdetkit verify mutation`: targeted mutation analysis for source files and changes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from sdetkit.changed_mutation import (
    DEFAULT_MAX_MUTANTS,
    HINTS,
    Mutant,
    applied,
    language,
    line_mutants,
    select_mutants,
)
from sdetkit.gates.project_env import resolve_project_python

JsonObject = dict[str, Any]


def _discover_source_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if language(str(target)) in ("python", "c") else []
    if target.is_dir():
        return sorted(p for p in target.rglob("*.py") if p.is_file())
    return []


def _run_test_suite(
    executable: str,
    args: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> tuple[bool, str, str]:
    env = {
        k: v for k, v in os.environ.items() if k not in ("PYTEST_ADDOPTS", "PYTEST_XDIST_WORKER")
    }
    cmd = [executable, "-m", "pytest", "-o", "addopts=", *args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        return proc.returncode == 0, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return False, "", "test suite timed out"
    except OSError as err:
        return False, "", str(err)


def run_targeted_mutation(
    root: Path,
    target_path: Path,
    pytest_args: list[str],
    *,
    max_mutants: int = DEFAULT_MAX_MUTANTS,
    min_score: float = 0.0,
    max_seconds: float | None = None,
    timeout: int = 60,
) -> JsonObject:
    files = _discover_source_files(target_path)
    if not files:
        return {
            "ok": True,
            "ran": False,
            "reason": f"no supported python files found under {target_path}",
            "score": 100.0,
            "killed": 0,
            "survived": 0,
            "total": 0,
            "mutants": [],
            "survivors": [],
        }

    sources: dict[str, str] = {}
    candidates: dict[str, dict[int, list[Mutant]]] = {}
    for file in files:
        rel = str(file.relative_to(root).as_posix())
        try:
            content = file.read_text(encoding="utf-8")
        except OSError:
            continue
        sources[rel] = content
        lines = list(range(1, len(content.splitlines()) + 1))
        found = line_mutants(rel, content, lines)
        if found:
            candidates[rel] = found

    chosen = select_mutants(candidates, sources, limit=max_mutants)
    if not chosen:
        return {
            "ok": True,
            "ran": True,
            "reason": "no mutable operators found in target files",
            "score": 100.0,
            "killed": 0,
            "survived": 0,
            "total": 0,
            "mutants": [],
            "survivors": [],
        }

    env = resolve_project_python(root)
    baseline_ok, out, err = _run_test_suite(env.executable, pytest_args, cwd=root, timeout=timeout)
    if not baseline_ok:
        return {
            "ok": False,
            "ran": False,
            "reason": f"baseline tests failed before mutation: {err.strip() or out.strip()}",
            "score": 0.0,
            "killed": 0,
            "survived": 0,
            "total": len(chosen),
            "mutants": [],
            "survivors": [],
        }

    start_time = time.monotonic()
    mutant_records: list[JsonObject] = []
    survivors: list[JsonObject] = []
    killed = 0
    survived = 0

    for mutant in chosen:
        if max_seconds is not None and (time.monotonic() - start_time) > max_seconds:
            break
        with applied(root, mutant):
            passed, _, _ = _run_test_suite(env.executable, pytest_args, cwd=root, timeout=timeout)
            outcome = "survived" if passed else "killed"

        hint = HINTS.get(mutant.kind, "")
        record = {
            "path": mutant.path,
            "line": mutant.line,
            "kind": mutant.kind,
            "before": mutant.before.strip(),
            "after": mutant.after.strip(),
            "outcome": outcome,
            "hint": hint,
        }
        mutant_records.append(record)
        if outcome == "killed":
            killed += 1
        else:
            survived += 1
            survivors.append(record)

    total = killed + survived
    score = round((killed / total) * 100, 1) if total else 100.0
    passed_gate = score >= min_score

    return {
        "ok": passed_gate,
        "ran": True,
        "score": score,
        "minimum": min_score,
        "killed": killed,
        "survived": survived,
        "total": total,
        "mutants": mutant_records,
        "survivors": survivors,
    }


def render_markdown(payload: JsonObject) -> str:
    if not payload.get("ran"):
        reason = payload.get("reason", "unknown error")
        return f"### SDETKit mutation testing: NOT RUN\n\n{reason}"

    score = payload.get("score", 0.0)
    killed = payload.get("killed", 0)
    total = payload.get("total", 0)
    survived = payload.get("survived", 0)
    min_score = payload.get("minimum", 0.0)
    ok = payload.get("ok", True)

    status_icon = "\u2705" if ok else "\u26a0\ufe0f"
    text = (
        f"### {status_icon} SDETKit mutation testing: {score}% ({killed}/{total} killed)\n\n"
        f"**Summary**: {killed} killed, {survived} survived (required threshold: {min_score}%).\n"
    )

    survivors = payload.get("survivors") or []
    if survivors:
        text += "\n**Surviving mutants (missing test assertions)**:\n"
        for s in survivors:
            text += (
                f"- `{s['path']}:{s['line']}`: `{s['before']}` \u2192 `{s['after']}`\n"
                f"  *Hint*: {s.get('hint', 'assert on this behavior')}\n"
            )
    else:
        text += "\nAll tested mutants were killed! Test assertions are thorough.\n"

    return text.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit verify mutation",
        description="Targeted mutation analysis on source files to detect gaps in test assertions.",
    )
    parser.add_argument(
        "--repo-root", default=".", help="Root directory of the repository (default: current dir)"
    )
    parser.add_argument(
        "--path",
        default=None,
        help="Path to a file or directory to mutate. If omitted, uses working tree change.",
    )
    parser.add_argument(
        "--max-mutants",
        type=int,
        default=DEFAULT_MAX_MUTANTS,
        help=f"Maximum mutants to synthesize (default {DEFAULT_MAX_MUTANTS})",
    )
    parser.add_argument(
        "--min-mutation-score",
        type=float,
        default=0.0,
        help="Minimum required mutation score percentage (default 0: report only)",
    )
    parser.add_argument(
        "--max-mutation-seconds",
        type=float,
        default=None,
        help="Maximum time budget in seconds for mutation testing",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument("--out", default=None, help="Write JSON report to this file")
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Arguments passed to pytest after -- (e.g. tests/test_file.py)",
    )

    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()

    if args.path:
        target = (root / args.path).resolve()
        payload = run_targeted_mutation(
            root=root,
            target_path=target,
            pytest_args=args.pytest_args,
            max_mutants=args.max_mutants,
            min_score=args.min_mutation_score,
            max_seconds=args.max_mutation_seconds,
        )
    else:
        # Fall back to verify change with working tree mutation
        from sdetkit import change_verifier

        verifier_args = [
            "--working-tree",
            "--repo-root",
            str(root),
            "--mutate",
            "--max-mutants",
            str(args.max_mutants),
            "--min-mutation-score",
            str(args.min_mutation_score),
            "--format",
            "json",
        ]
        if args.max_mutation_seconds:
            verifier_args.extend(["--max-mutation-seconds", str(args.max_mutation_seconds)])
        if args.pytest_args:
            verifier_args.extend(["--", *args.pytest_args])

        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            change_verifier.main(verifier_args)
        try:
            report = json.loads(buf.getvalue() or "{}")
        except ValueError:
            report = {}

        mutation_data = report.get("mutation") or {}
        score = mutation_data.get("score")
        mutants = mutation_data.get("mutants") or []
        survivors = [m for m in mutants if m.get("outcome") == "survived"]
        payload = {
            "ok": (score or 0.0) >= args.min_mutation_score,
            "ran": bool(mutation_data.get("ran")),
            "score": score or 0.0,
            "minimum": args.min_mutation_score,
            "killed": sum(1 for m in mutants if m.get("outcome") == "killed"),
            "survived": len(survivors),
            "total": len(mutants),
            "mutants": mutants,
            "survivors": survivors,
        }

    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(render_markdown(payload))

    return 0 if payload.get("ok", True) else 1
