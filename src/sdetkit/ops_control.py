from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from . import _toml
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .atomicio import atomic_write_text
from .plugin_system import discover


@dataclass(frozen=True)
class TaskDef:
    name: str
    command: tuple[str, ...]
    deps: tuple[str, ...] = ()
    offline_only: bool = True


BUILTIN_TASKS: dict[str, TaskDef] = {
    "quality": TaskDef("quality", ("bash", "quality.sh")),
    "ci": TaskDef("ci", ("bash", "ci.sh"), deps=("quality",)),
    "doctor": TaskDef("doctor", ("python3", "-m", "sdetkit", "doctor", "--ascii")),
    "repo-audit": TaskDef(
        "repo-audit",
        (
            "python3",
            "-m",
            "sdetkit",
            "repo",
            "audit",
            ".",
            "--format",
            "json",
            "--fail-on",
            "none",
            "--output",
            ".sdetkit/out/repo-audit.json",
            "--force",
        ),
    ),
    "security-scan": TaskDef(
        "security-scan",
        (
            "python3",
            "-m",
            "sdetkit",
            "security",
            "scan",
            "--fail-on",
            "none",
            "--format",
            "sarif",
            "--output",
            ".sdetkit/out/security.sarif",
        ),
    ),
    "security-fix": TaskDef(
        "security-fix",
        ("python3", "-m", "sdetkit", "security", "fix", "--dry-run"),
        deps=("security-scan",),
    ),
    "report-build": TaskDef(
        "report-build",
        (
            "python3",
            "-m",
            "sdetkit",
            "report",
            "build",
            "--history-dir",
            ".",
            "--format",
            "md",
            "--output",
            ".sdetkit/out/report.md",
        ),
        deps=("repo-audit", "doctor", "security-scan"),
    ),
}
PROFILES = {
    "default": ("quality", "doctor", "repo-audit", "security-scan", "report-build"),
    "ci": (
        "quality",
        "ci",
        "doctor",
        "repo-audit",
        "security-scan",
        "security-fix",
        "report-build",
    ),
    "local": ("quality", "doctor", "repo-audit", "report-build"),
}


def _root() -> Path:
    return Path.cwd()


def _sdetkit_dir() -> Path:
    return _root() / ".sdetkit"


def init_layout(force: bool = False) -> int:
    base = _sdetkit_dir()
    for rel in ("policies", "playbooks", "cache", "out"):
        (base / rel).mkdir(parents=True, exist_ok=True)
    cfg = base / "config.toml"
    if cfg.exists() and not force:
        return 0
    text = (
        "[ops]\n"
        'default_profile = "default"\n'
        "[profiles]\n"
        'default = ["quality", "doctor", "repo-audit", "security-scan", "report-build"]\n'
        'ci = ["quality", "ci", "doctor", "repo-audit", "security-scan", "security-fix", "report-build"]\n'
        'local = ["quality", "doctor", "repo-audit", "report-build"]\n'
    )
    atomic_write_text(cfg, text)
    return 0


def _load_config() -> dict[str, Any]:
    cfg = _sdetkit_dir() / "config.toml"
    if not cfg.is_file():
        return {}
    return _toml.loads(cfg.read_text(encoding="utf-8"))


def _task_catalog() -> dict[str, TaskDef]:
    tasks = dict(BUILTIN_TASKS)
    for record in discover("sdetkit.ops_tasks", "ops_tasks", _root()):
        try:
            loaded = record.factory()
            if isinstance(loaded, TaskDef):
                tasks[loaded.name] = loaded
        except Exception:
            continue
    return tasks


def _task_order(tasks: dict[str, TaskDef], selected: tuple[str, ...]) -> list[str]:
    indegree = {name: 0 for name in selected}
    dependents: dict[str, list[str]] = {name: [] for name in selected}
    for name in selected:
        for dep in tasks[name].deps:
            if dep not in indegree:
                continue
            indegree[name] += 1
            dependents[dep].append(name)
    ready = sorted([k for k, v in indegree.items() if v == 0])
    out: list[str] = []
    while ready:
        cur = ready.pop(0)
        out.append(cur)
        for nxt in sorted(dependents[cur]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
                ready.sort()
    return out


def _profile_tasks(profile: str) -> tuple[str, ...]:
    cfg = _load_config()
    configured = (
        cfg.get("profiles", {}).get(profile) if isinstance(cfg.get("profiles"), dict) else None
    )
    if isinstance(configured, list) and all(isinstance(i, str) for i in configured):
        return tuple(configured)
    return PROFILES[profile]


def _inputs_hash(task: TaskDef, profile: str, apply: bool) -> str:
    h = hashlib.sha256()
    h.update(profile.encode())
    h.update(("apply" if apply else "dry").encode())
    h.update("\0".join(task.command).encode())
    for p in sorted(_root().glob("**/*.py"), key=lambda i: i.as_posix()):
        if "/.git/" in p.as_posix() or p.is_dir():
            continue
        h.update(p.as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def _cache_status(task: TaskDef, key: str) -> bool:
    cp = _sdetkit_dir() / "cache" / f"{task.name}.json"
    if not cp.is_file():
        return False
    try:
        payload = json.loads(cp.read_text(encoding="utf-8"))
    except ValueError:
        return False
    return bool(payload.get("key") == key and payload.get("status") == "PASS")


def _write_cache(task: TaskDef, key: str, status: str, summary: str) -> None:
    cp = _sdetkit_dir() / "cache" / f"{task.name}.json"
    cp.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        cp,
        json.dumps({"key": key, "status": status, "summary": summary}, sort_keys=True, indent=2)
        + "\n",
    )


def plan(profile: str, apply: bool, no_cache: bool) -> list[dict[str, Any]]:
    tasks = _task_catalog()
    selected = _profile_tasks(profile)
    ordered = _task_order(tasks, selected)
    out: list[dict[str, Any]] = []
    for name in ordered:
        task = tasks[name]
        key = _inputs_hash(task, profile, apply)
        cached = False if no_cache else _cache_status(task, key)
        out.append(
            {
                "task": name,
                "cached": cached,
                "offline_only": task.offline_only,
                "deps": list(task.deps),
            }
        )
    return out


def run(
    profile: str, jobs: int, apply: bool, no_cache: bool, fail_fast: bool, keep_going: bool
) -> int:
    tasks = _task_catalog()
    selected = _profile_tasks(profile)
    ordered = _task_order(tasks, selected)
    statuses: dict[str, str] = {}
    outputs: dict[str, str] = {}
    keys = {name: _inputs_hash(tasks[name], profile, apply) for name in ordered}

    deps = {name: [d for d in tasks[name].deps if d in ordered] for name in ordered}
    remaining = set(ordered)
    failed = False

    def execute(name: str) -> tuple[str, str, str]:
        task = tasks[name]
        if not no_cache and _cache_status(task, keys[name]):
            return name, "CACHED", "cache hit"
        cmd = list(task.command)
        if name == "security-fix" and apply:
            cmd = ["python3", "-m", "sdetkit", "security", "fix", "--apply"]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        out_text = (proc.stdout or "") + (proc.stderr or "")
        return name, ("PASS" if proc.returncode == 0 else "FAIL"), out_text

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures: dict[Any, str] = {}
        while remaining:
            ready = [
                n
                for n in sorted(remaining)
                if all(statuses.get(d) in {"PASS", "CACHED"} for d in deps[n])
            ]
            if not ready and not futures:
                for n in sorted(remaining):
                    statuses[n] = "SKIPPED"
                    outputs[n] = "dependency failed"
                break
            for name in ready:
                if len(futures) >= max(1, jobs):
                    break
                futures[pool.submit(execute, name)] = name
                remaining.remove(name)
            if not futures:
                continue
            done, _ = wait(set(futures), return_when=FIRST_COMPLETED)
            for fut in done:
                name, status, out_text = fut.result()
                statuses[name] = status
                outputs[name] = out_text
                if status == "PASS":
                    _write_cache(tasks[name], keys[name], status, "ok")
                elif status == "CACHED":
                    pass
                else:
                    failed = True
                    _write_cache(tasks[name], keys[name], status, "failed")
                    if fail_fast and not keep_going:
                        for rest in sorted(remaining):
                            statuses[rest] = "SKIPPED"
                            outputs[rest] = "stopped by --fail-fast"
                        remaining.clear()
                del futures[fut]

    out_dir = _sdetkit_dir() / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ordered:
        atomic_write_text(out_dir / f"{name}.log", outputs.get(name, ""))

    for name in ordered:
        print(f"[{statuses.get(name, 'SKIPPED')}] {name}")
        if statuses.get(name) == "FAIL":
            print(f"  next: inspect .sdetkit/out/{name}.log and run task command locally")
    return 1 if failed else 0


def cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit ops")
    sub = p.add_subparsers(dest="cmd", required=True)
    init_p = sub.add_parser("init")
    init_p.add_argument("--force", action="store_true")
    plan_p = sub.add_parser("plan")
    plan_p.add_argument("--profile", choices=["default", "ci", "local"], default="default")
    plan_p.add_argument("--apply", action="store_true")
    plan_p.add_argument("--dry-run", action="store_true")
    plan_p.add_argument("--no-cache", action="store_true")
    run_p = sub.add_parser("run")
    run_p.add_argument("--profile", choices=["default", "ci", "local"], default="default")
    run_p.add_argument("--jobs", type=int, default=1)
    run_p.add_argument("--dry-run", action="store_true")
    run_p.add_argument("--apply", action="store_true")
    run_p.add_argument("--no-cache", action="store_true")
    run_p.add_argument("--fail-fast", action="store_true")
    run_p.add_argument("--keep-going", action="store_true")

    ns = p.parse_args(argv)
    if ns.cmd == "init":
        return init_layout(force=bool(ns.force))
    if ns.cmd == "plan":
        init_layout(force=False)
        payload = plan(ns.profile, apply=bool(ns.apply), no_cache=bool(ns.no_cache))
        print(json.dumps({"profile": ns.profile, "plan": payload}, sort_keys=True, indent=2))
        return 0
    init_layout(force=False)
    apply = bool(ns.apply) and not bool(ns.dry_run)
    ff = bool(ns.fail_fast) or (ns.profile == "ci" and not ns.keep_going)
    return run(ns.profile, ns.jobs, apply, bool(ns.no_cache), ff, bool(ns.keep_going))
