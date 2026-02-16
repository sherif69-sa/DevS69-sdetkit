from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import queue
import re
import shutil
import subprocess
import threading
import time
import tomllib
import urllib.parse
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .atomicio import atomic_write_text
from .doctor import _scan_non_ascii
from .repo import run_repo_audit
from .report import build_run_record
from .security import safe_path
from .security_gate import scan_repo

_UTC = dt.UTC
_VAR_RE = re.compile(r"\$\{([^}]+)\}")


@dataclasses.dataclass(frozen=True)
class Policy:
    allow_shell: bool = False
    allow_artifact_escape: bool = False


@dataclasses.dataclass(frozen=True)
class StepDef:
    id: str
    type: str
    inputs: dict[str, Any]
    outputs: dict[str, str]
    depends_on: tuple[str, ...]
    policy: dict[str, Any]


@dataclasses.dataclass(frozen=True)
class WorkflowDef:
    name: str
    version: str
    steps: tuple[StepDef, ...]
    policy: Policy


@dataclasses.dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    policy_requirements: dict[str, Any]
    func: Callable[[dict[str, Any]], dict[str, Any]]


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, ActionSpec] = {}

    def register(self, action: ActionSpec) -> None:
        self._actions[action.name] = action

    def get(self, name: str) -> ActionSpec:
        if name not in self._actions:
            raise ValueError(f"unknown action: {name}")
        return self._actions[name]

    def list_specs(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for name in sorted(self._actions):
            spec = self._actions[name]
            out.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "input_schema": spec.input_schema,
                    "output_schema": spec.output_schema,
                    "policy_requirements": spec.policy_requirements,
                }
            )
        return out


def _action_repo_audit(inputs: dict[str, Any]) -> dict[str, Any]:
    root = Path(str(inputs.get("root", "."))).resolve()
    payload = run_repo_audit(root)
    return {
        "summary": payload.get("summary", {}),
        "findings": payload.get("findings", []),
        "suppressed": payload.get("suppressed", []),
    }


def _action_security_scan(inputs: dict[str, Any]) -> dict[str, Any]:
    root = Path(str(inputs.get("root", "."))).resolve()
    findings = scan_repo(root)
    return {
        "findings": [dataclasses.asdict(item) for item in findings],
        "counts": {"total": len(findings)},
    }


def _action_security_check(inputs: dict[str, Any]) -> dict[str, Any]:
    payload = _action_security_scan(inputs)
    payload["ok"] = payload["counts"]["total"] == 0
    return payload


def _action_doctor_ascii(inputs: dict[str, Any]) -> dict[str, Any]:
    root = Path(str(inputs.get("root", "."))).resolve()
    files, stderr = _scan_non_ascii(root)
    return {"ok": not files, "non_ascii_files": files, "diagnostics": stderr}


def _action_report_build(inputs: dict[str, Any]) -> dict[str, Any]:
    audit_payload = dict(inputs.get("audit", {})) if isinstance(inputs.get("audit"), dict) else {}
    root = str(inputs.get("repo_root", "."))
    record = build_run_record(
        audit_payload,
        profile=str(inputs.get("profile", "default")),
        packs=("core",),
        fail_on="none",
        repo_root=root,
        config_used=None,
    )
    output = Path(str(inputs.get("output", "report.json")))
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, json.dumps(record, sort_keys=True, indent=2) + "\n")
    return {"report_path": output.as_posix(), "record": record}


def build_registry() -> ActionRegistry:
    reg = ActionRegistry()
    reg.register(
        ActionSpec(
            name="repo.audit",
            description="Run repository audit checks",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            policy_requirements={},
            func=_action_repo_audit,
        )
    )
    reg.register(
        ActionSpec(
            name="report.build",
            description="Build run report",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            policy_requirements={},
            func=_action_report_build,
        )
    )
    reg.register(
        ActionSpec(
            name="security.scan",
            description="Security scan",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            policy_requirements={},
            func=_action_security_scan,
        )
    )
    reg.register(
        ActionSpec(
            name="security.check",
            description="Security check",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            policy_requirements={"risk": "security"},
            func=_action_security_check,
        )
    )
    reg.register(
        ActionSpec(
            name="doctor.ascii",
            description="ASCII doctor scan",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            policy_requirements={},
            func=_action_doctor_ascii,
        )
    )
    return reg


def _resolve_workflow_path(path: Path) -> Path:
    candidate = Path(path)
    if any(part == ".." for part in candidate.parts):
        raise ValueError("workflow path traversal is not allowed")

    base = Path.cwd()
    # Workflows may be provided via temporary absolute paths (for tests/automation).
    # `safe_path` still enforces traversal and NUL protections.
    resolved = safe_path(base, str(candidate), allow_absolute=True)

    if resolved.suffix.lower() not in {".toml", ".json"}:
        raise ValueError("workflow path must end with .toml or .json")
    if not resolved.is_file():
        raise ValueError(f"workflow path does not exist: {resolved}")
    return resolved


def _validate_run_id(run_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", run_id):
        raise ValueError("invalid run id")
    return run_id


def _load_workflow(path: Path) -> WorkflowDef:
    if path.suffix.lower() == ".json":
        doc = json.loads(path.read_text(encoding="utf-8"))
    else:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("workflow"), dict):
        raise ValueError("workflow document must include [workflow]")
    w = dict(doc["workflow"])
    steps_obj = w.get("steps", [])
    if not isinstance(steps_obj, list):
        raise ValueError("workflow.steps must be an array")
    steps: list[StepDef] = []
    seen: set[str] = set()
    for step_obj in steps_obj:
        if not isinstance(step_obj, dict):
            raise ValueError("step must be object")
        sid = str(step_obj.get("id", "")).strip()
        if not sid or sid in seen:
            raise ValueError(f"duplicate/empty step id: {sid}")
        seen.add(sid)
        depends_on_obj = step_obj.get("depends_on", [])
        depends_on = (
            tuple(str(x) for x in depends_on_obj) if isinstance(depends_on_obj, list) else tuple()
        )
        steps.append(
            StepDef(
                id=sid,
                type=str(step_obj.get("type", "")),
                inputs=dict(step_obj.get("inputs", {}))
                if isinstance(step_obj.get("inputs"), dict)
                else {},
                outputs=dict(step_obj.get("outputs", {}))
                if isinstance(step_obj.get("outputs"), dict)
                else {},
                depends_on=depends_on,
                policy=dict(step_obj.get("policy", {}))
                if isinstance(step_obj.get("policy"), dict)
                else {},
            )
        )
    policy_obj = w.get("policy", {})
    policy = Policy(
        allow_shell=bool(policy_obj.get("allow_shell", False))
        if isinstance(policy_obj, dict)
        else False,
        allow_artifact_escape=bool(policy_obj.get("allow_artifact_escape", False))
        if isinstance(policy_obj, dict)
        else False,
    )
    wf = WorkflowDef(
        name=str(w.get("name", path.stem)),
        version=str(w.get("version", "1")),
        steps=tuple(steps),
        policy=policy,
    )
    _validate_graph(wf)
    return wf


def _validate_graph(wf: WorkflowDef) -> None:
    by_id = {step.id: step for step in wf.steps}
    state: dict[str, int] = {k: 0 for k in by_id}

    def visit(node: str) -> None:
        if node not in by_id:
            raise ValueError(f"unknown dependency: {node}")
        if state[node] == 1:
            raise ValueError("cycle detected")
        if state[node] == 2:
            return
        state[node] = 1
        for dep in by_id[node].depends_on:
            visit(dep)
        state[node] = 2

    for sid in sorted(by_id):
        visit(sid)


def _interpolate(value: Any, ctx: Mapping[str, Any]) -> Any:
    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            parts = key.split(".")
            cur: Any = ctx
            for p in parts:
                if isinstance(cur, Mapping) and p in cur:
                    cur = cur[p]
                else:
                    raise ValueError(f"unknown interpolation variable: {key}")
            return str(cur)

        return _VAR_RE.sub(repl, value)
    if isinstance(value, list):
        return [_interpolate(x, ctx) for x in value]
    if isinstance(value, dict):
        return {str(k): _interpolate(v, ctx) for k, v in value.items()}
    return value


def _resolve_order(wf: WorkflowDef) -> list[str]:
    indegree: dict[str, int] = {step.id: 0 for step in wf.steps}
    reverse: dict[str, list[str]] = {step.id: [] for step in wf.steps}
    for step in wf.steps:
        for dep in step.depends_on:
            indegree[step.id] += 1
            reverse[dep].append(step.id)
    ready = sorted([k for k, v in indegree.items() if v == 0])
    out: list[str] = []
    while ready:
        cur = ready.pop(0)
        out.append(cur)
        for nxt in sorted(reverse[cur]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
                ready.sort()
    if len(out) != len(wf.steps):
        raise ValueError("cycle detected")
    return out


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_id(workflow_text: str, inputs: dict[str, Any]) -> str:
    ts = dt.datetime.now(tz=_UTC).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(
        (workflow_text + json.dumps(inputs, sort_keys=True)).encode("utf-8")
    ).hexdigest()[:12]
    return f"{ts}-{digest}"


def _step_execute(
    step: StepDef,
    *,
    ctx: dict[str, Any],
    artifacts_dir: Path,
    policy: Policy,
    registry: ActionRegistry,
) -> dict[str, Any]:
    started = time.time()
    resolved_inputs = _interpolate(step.inputs, ctx)
    findings: list[dict[str, Any]] = []
    status = "ok"
    output: dict[str, Any] = {}

    if step.type == "python_call":
        action = str(resolved_inputs.get("action", ""))
        kwargs = (
            dict(resolved_inputs.get("kwargs", {}))
            if isinstance(resolved_inputs.get("kwargs"), dict)
            else {}
        )
        if action in {"security.check", "security.scan"}:
            findings.append(
                {
                    "type": "red_flag",
                    "message": f"risky action requested: {action}",
                    "severity": "warn",
                }
            )
        spec = registry.get(action)
        output = spec.func(kwargs)
    elif step.type == "command":
        cmd = resolved_inputs.get("cmd", [])
        if not isinstance(cmd, list):
            raise ValueError("command.cmd must be list")
        shell = bool(resolved_inputs.get("shell", False))
        if shell and not policy.allow_shell:
            raise ValueError("policy blocks shell=true")
        if shell:
            findings.append(
                {"type": "red_flag", "message": "shell=true command", "severity": "warn"}
            )
        if shell:
            cmd_text = " ".join(str(x) for x in cmd)
            proc = subprocess.run(
                ["/bin/sh", "-c", cmd_text],
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            proc = subprocess.run(
                [str(x) for x in cmd],
                capture_output=True,
                text=True,
                check=False,
            )
        output = {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
        if proc.returncode != 0:
            status = "error"
    elif step.type == "write_file":
        rel = str(resolved_inputs.get("path", "output.txt"))
        target = safe_path(artifacts_dir, rel, allow_absolute=policy.allow_artifact_escape)
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, str(resolved_inputs.get("text", "")))
        output = {"path": target.as_posix(), "sha256": _sha256_file(target)}
    elif step.type == "read_file":
        rel = str(resolved_inputs.get("path", ""))
        target = safe_path(artifacts_dir, rel, allow_absolute=False)
        output = {"path": target.as_posix(), "text": target.read_text(encoding="utf-8")}
    elif step.type == "render_report":
        payload = _action_report_build(dict(resolved_inputs))
        output = payload
    else:
        raise ValueError(f"unknown step type: {step.type}")

    return {
        "step_id": step.id,
        "type": step.type,
        "status": status,
        "inputs": resolved_inputs,
        "outputs": output,
        "findings": findings,
        "duration_ms": int((time.time() - started) * 1000),
    }


def run_workflow(
    workflow_path: Path,
    *,
    inputs: dict[str, Any],
    artifacts_dir: Path,
    history_dir: Path,
    workers: int,
    dry_run: bool,
    fail_fast: bool,
    registry: ActionRegistry | None = None,
) -> dict[str, Any]:
    registry = registry or build_registry()
    resolved_workflow_path = _resolve_workflow_path(workflow_path)
    workflow_text = resolved_workflow_path.read_text(encoding="utf-8")
    wf = _load_workflow(resolved_workflow_path)
    run_id = _run_id(workflow_text, inputs)
    run_root = history_dir / ".sdetkit" / "ops-history" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    artifacts_run_dir = run_root / "artifacts"
    artifacts_run_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    plan_order = _resolve_order(wf)
    by_id = {step.id: step for step in wf.steps}
    deps = {step.id: set(step.depends_on) for step in wf.steps}
    dependents: dict[str, set[str]] = {step.id: set() for step in wf.steps}
    for sid, dep_set in deps.items():
        for dep in dep_set:
            dependents[dep].add(sid)

    ctx: dict[str, Any] = {"input": inputs, "step": {}}
    events: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    ready = queue.PriorityQueue[tuple[str, str]]()
    for sid, dep_set in deps.items():
        if not dep_set:
            ready.put((sid, sid))
    lock = threading.Lock()
    pending: set[str] = set()

    def submit_step(sid: str) -> dict[str, Any]:
        step = by_id[sid]
        if dry_run:
            return {
                "step_id": sid,
                "type": step.type,
                "status": "dry_run",
                "inputs": step.inputs,
                "outputs": {},
                "findings": [],
                "duration_ms": 0,
            }
        return _step_execute(
            step, ctx=ctx, artifacts_dir=artifacts_run_dir, policy=wf.policy, registry=registry
        )

    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        futures: dict[Any, str] = {}
        while len(results) < len(wf.steps):
            while not ready.empty() and len(futures) < max(workers, 1):
                _, sid = ready.get()
                if sid in pending or sid in results:
                    continue
                pending.add(sid)
                events.append(
                    {
                        "event": "step_scheduled",
                        "step_id": sid,
                        "ts": dt.datetime.now(tz=_UTC).isoformat(),
                    }
                )
                futures[pool.submit(submit_step, sid)] = sid
            if not futures:
                break
            done, _ = wait(set(futures.keys()), return_when=FIRST_COMPLETED)
            for fut in done:
                sid = futures.pop(fut)
                pending.discard(sid)
                result = fut.result()
                with lock:
                    results[sid] = result
                    ctx["step"][sid] = result.get("outputs", {})
                events.append(
                    {
                        "event": "step_finished",
                        "step_id": sid,
                        "status": result.get("status"),
                        "ts": dt.datetime.now(tz=_UTC).isoformat(),
                    }
                )
                if fail_fast and result.get("status") == "error":
                    futures.clear()
                    break
                for child in sorted(dependents[sid]):
                    deps[child].discard(sid)
                    if not deps[child]:
                        ready.put((child, child))

    ordered_results = {sid: results[sid] for sid in plan_order if sid in results}
    artifact_index = []
    for fp in sorted(artifacts_run_dir.rglob("*") if artifacts_run_dir.exists() else []):
        if fp.is_file():
            artifact_index.append(
                {"path": fp.relative_to(artifacts_run_dir).as_posix(), "sha256": _sha256_file(fp)}
            )

    run_doc = {
        "run_id": run_id,
        "workflow": dataclasses.asdict(wf),
        "workflow_path": resolved_workflow_path.as_posix(),
        "inputs": inputs,
        "plan": plan_order,
        "environment": {"cwd": Path.cwd().as_posix()},
    }
    results_doc = {
        "run_id": run_id,
        "workflow_name": wf.name,
        "status": "ok"
        if all(item.get("status") in {"ok", "dry_run"} for item in ordered_results.values())
        else "error",
        "steps": ordered_results,
        "artifacts": artifact_index,
    }

    atomic_write_text(run_root / "run.json", json.dumps(run_doc, sort_keys=True, indent=2) + "\n")
    atomic_write_text(
        run_root / "results.json", json.dumps(results_doc, sort_keys=True, indent=2) + "\n"
    )
    atomic_write_text(
        run_root / "events.jsonl", "".join(json.dumps(e, sort_keys=True) + "\n" for e in events)
    )
    if artifacts_dir != artifacts_run_dir:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        for fp in artifacts_run_dir.rglob("*"):
            if fp.is_file():
                rel = fp.relative_to(artifacts_run_dir)
                dest = artifacts_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fp, dest)
    return results_doc


def _history_root(history_dir: Path) -> Path:
    return history_dir / ".sdetkit" / "ops-history"


def list_runs(history_dir: Path) -> list[dict[str, Any]]:
    root = _history_root(history_dir)
    if not root.exists():
        return []
    out: list[dict[str, Any]] = []
    for run_dir in sorted(root.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        results_path = run_dir / "results.json"
        if not results_path.exists():
            continue
        doc = json.loads(results_path.read_text(encoding="utf-8"))
        out.append(
            {
                "run_id": run_dir.name,
                "workflow_name": doc.get("workflow_name", ""),
                "status": doc.get("status", "unknown"),
            }
        )
    return out


def load_run(history_dir: Path, run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    valid_run_id = _validate_run_id(run_id)
    history_root = _history_root(history_dir)
    run_dir = safe_path(history_root, valid_run_id, allow_absolute=False)
    run_doc = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    results_doc = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    return run_doc, results_doc


def replay_run(history_dir: Path, run_id: str, workers: int = 1) -> dict[str, Any]:
    run_doc, _ = load_run(history_dir, run_id)
    path = Path(str(run_doc["workflow_path"]))
    return run_workflow(
        path,
        inputs=dict(run_doc.get("inputs", {})),
        artifacts_dir=history_dir / ".sdetkit" / "ops-replay-artifacts",
        history_dir=history_dir,
        workers=workers,
        dry_run=False,
        fail_fast=False,
    )


def diff_runs(history_dir: Path, run_a: str, run_b: str) -> dict[str, Any]:
    _, a = load_run(history_dir, run_a)
    _, b = load_run(history_dir, run_b)
    a_steps = a.get("steps", {})
    b_steps = b.get("steps", {})
    changed_steps: list[str] = []
    for sid in sorted(set(a_steps) | set(b_steps)):
        if a_steps.get(sid) != b_steps.get(sid):
            changed_steps.append(sid)
    a_art = {x["path"]: x["sha256"] for x in a.get("artifacts", [])}
    b_art = {x["path"]: x["sha256"] for x in b.get("artifacts", [])}
    changed_artifacts = sorted([p for p in set(a_art) | set(b_art) if a_art.get(p) != b_art.get(p)])

    def _findings_count(doc: dict[str, Any]) -> int:
        total = 0
        for step in doc.get("steps", {}).values():
            out = step.get("outputs", {}) if isinstance(step, dict) else {}
            if isinstance(out, dict) and isinstance(out.get("findings"), list):
                total += len(out["findings"])
        return total

    return {
        "run_a": run_a,
        "run_b": run_b,
        "changed_steps": changed_steps,
        "changed_artifacts": changed_artifacts,
        "audit_security_finding_delta": _findings_count(b) - _findings_count(a),
    }


def _templates() -> dict[str, str]:
    root = Path("tools/workflows/templates")
    out: dict[str, str] = {}
    if root.exists():
        for fp in sorted(root.glob("*.toml")):
            out[fp.stem] = fp.read_text(encoding="utf-8")
    return out


def _parse_http_path(raw_path: str) -> tuple[str, dict[str, list[str]]]:
    parsed = urllib.parse.urlparse(raw_path)
    return parsed.path, urllib.parse.parse_qs(parsed.query, keep_blank_values=True)


def _safe_run_id(path: str) -> str | None:
    if not path.startswith("/runs/"):
        return None
    run_id = urllib.parse.unquote(path.split("/", 2)[2])
    try:
        return _validate_run_id(run_id)
    except ValueError:
        return None


class _OpsHandler(BaseHTTPRequestHandler):
    registry: ActionRegistry
    history_dir: Path

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path, _query = _parse_http_path(self.path)
        if path == "/health":
            self._json(200, {"ok": True})
            return
        if path == "/actions":
            self._json(200, {"actions": self.registry.list_specs()})
            return
        if path == "/runs":
            self._json(200, {"runs": list_runs(self.history_dir)})
            return
        if path.startswith("/runs/"):
            run_id = _safe_run_id(path)
            if run_id is None:
                self._json(400, {"error": "invalid run id"})
                return
            try:
                run_doc, results_doc = load_run(self.history_dir, run_id)
            except OSError as exc:
                self._json(404, {"error": str(exc)})
                return
            self._json(200, {"run": run_doc, "results": results_doc})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path, _query = _parse_http_path(self.path)
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            self._json(400, {"error": "invalid json"})
            return
        if path == "/run-action":
            try:
                action = self.registry.get(str(payload.get("action", "")))
                inputs = (
                    dict(payload.get("inputs", {}))
                    if isinstance(payload.get("inputs"), dict)
                    else {}
                )
                out = action.func(inputs)
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"error": str(exc)})
                return
            self._json(200, {"outputs": out})
            return
        if path == "/run-workflow":
            try:
                workflow_path = Path(str(payload.get("workflow_path", "")))
                inputs = (
                    dict(payload.get("inputs", {}))
                    if isinstance(payload.get("inputs"), dict)
                    else {}
                )
                out = run_workflow(
                    workflow_path,
                    inputs=inputs,
                    artifacts_dir=Path("artifacts"),
                    history_dir=self.history_dir,
                    workers=1,
                    dry_run=False,
                    fail_fast=False,
                    registry=self.registry,
                )
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"error": str(exc)})
                return
            self._json(200, out)
            return
        self._json(404, {"error": "not found"})


def serve(host: str, port: int, history_dir: Path) -> None:
    _OpsHandler.registry = build_registry()
    _OpsHandler.history_dir = history_dir
    server = ThreadingHTTPServer((host, port), _OpsHandler)
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit ops")
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("workflow_path")
    run_p.add_argument("--inputs", default="{}")
    run_p.add_argument("--artifacts-dir", default="artifacts")
    run_p.add_argument("--history-dir", default=".")
    run_p.add_argument("--workers", type=int, default=1)
    run_p.add_argument("--dry-run", action="store_true")
    run_p.add_argument("--fail-fast", action="store_true")

    replay_p = sub.add_parser("replay")
    replay_p.add_argument("run_id")
    replay_p.add_argument("--history-dir", default=".")

    diff_p = sub.add_parser("diff")
    diff_p.add_argument("run_id_a")
    diff_p.add_argument("run_id_b")
    diff_p.add_argument("--history-dir", default=".")
    diff_p.add_argument("--format", choices=["text", "json"], default="text")

    list_p = sub.add_parser("list")
    list_p.add_argument("--history-dir", default=".")

    init_p = sub.add_parser("init-template")
    init_p.add_argument("name")
    init_p.add_argument("--output", required=True)

    serve_p = sub.add_parser("serve")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8765)
    serve_p.add_argument("--history-dir", default=".")

    ns = p.parse_args(argv)
    if ns.cmd == "run":
        in_obj = json.loads(str(ns.inputs))
        if not isinstance(in_obj, dict):
            raise ValueError("--inputs must be a JSON object")
        out = run_workflow(
            Path(ns.workflow_path),
            inputs=in_obj,
            artifacts_dir=Path(ns.artifacts_dir),
            history_dir=Path(ns.history_dir),
            workers=ns.workers,
            dry_run=bool(ns.dry_run),
            fail_fast=bool(ns.fail_fast),
        )
        print(json.dumps(out, sort_keys=True, indent=2))
        return 0
    if ns.cmd == "replay":
        out = replay_run(Path(ns.history_dir), ns.run_id)
        print(json.dumps(out, sort_keys=True, indent=2))
        return 0
    if ns.cmd == "diff":
        out = diff_runs(Path(ns.history_dir), ns.run_id_a, ns.run_id_b)
        if ns.format == "json":
            print(json.dumps(out, sort_keys=True, indent=2))
        else:
            print(
                f"changed_steps={len(out['changed_steps'])} changed_artifacts={len(out['changed_artifacts'])} delta={out['audit_security_finding_delta']}"
            )
        return 0
    if ns.cmd == "list":
        print(json.dumps({"runs": list_runs(Path(ns.history_dir))}, sort_keys=True, indent=2))
        return 0
    if ns.cmd == "init-template":
        templates = _templates()
        if ns.name not in templates:
            raise ValueError(
                f"unknown template {ns.name}; available: {', '.join(sorted(templates))}"
            )
        out_path = Path(ns.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(out_path, templates[ns.name])
        print(out_path)
        return 0
    if ns.cmd == "serve":
        serve(str(ns.host), int(ns.port), Path(ns.history_dir))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
