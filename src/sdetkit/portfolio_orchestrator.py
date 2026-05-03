from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_repo_graph(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("repo graph must be a JSON object")
    repos = payload.get("repos")
    if not isinstance(repos, list) or not repos:
        raise ValueError("repo graph must include a non-empty repos array")
    return payload


def _validate_repo_graph_shape(payload: dict[str, Any]) -> None:
    repos = payload.get("repos")
    if not isinstance(repos, list) or not repos:
        raise ValueError("repos must be a non-empty array")
    names: set[str] = set()
    for repo in repos:
        if not isinstance(repo, dict):
            raise ValueError("each repo must be an object")
        for field in ("name", "path", "language"):
            value = repo.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"repo field '{field}' must be a non-empty string")
        name = str(repo["name"])
        if name in names:
            raise ValueError(f"duplicate repo name '{name}'")
        names.add(name)


def _validate_against_repo_schema(payload: dict[str, Any], schema_path: Path) -> None:
    schema_payload = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore
    except Exception:
        # Fallback path for environments without jsonschema dependency.
        _validate_repo_graph_shape(payload)
        return
    jsonschema.validate(instance=payload, schema=schema_payload)


def _build_plan(graph: dict[str, object], max_workers: int) -> dict[str, object]:
    repos = graph.get("repos", [])
    assert isinstance(repos, list)
    names = {
        str(repo.get("name"))
        for repo in repos
        if isinstance(repo, dict) and isinstance(repo.get("name"), str)
    }
    for repo in repos:
        if not isinstance(repo, dict):
            continue
        deps = repo.get("depends_on", [])
        if not isinstance(deps, list):
            raise ValueError("depends_on must be an array when provided")
        for dep in deps:
            if str(dep) not in names:
                raise ValueError(f"unknown dependency '{dep}' for repo '{repo.get('name')}'")

    plan_items: list[dict[str, object]] = []
    queued = sorted(
        (repo for repo in repos if isinstance(repo, dict)),
        key=lambda item: int(item.get("priority", 100)),
    )
    done: set[str] = set()
    batch_index = 0
    while queued:
        progressed = False
        for repo in list(queued):
            deps = repo.get("depends_on", [])
            assert isinstance(deps, list)
            if any(str(dep) not in done for dep in deps):
                continue
            name = str(repo.get("name", f"repo-{len(done)+1}"))
            language = str(repo.get("language", "unknown"))
            lane = "gate+review" if language.lower() in {"python", "node", "go"} else "gate"
            plan_items.append(
                {
                    "repo": name,
                    "path": str(repo.get("path", f"repos/{name}")),
                    "language": language,
                    "lane": lane,
                    "priority": int(repo.get("priority", 100)),
                    "depends_on": [str(dep) for dep in deps],
                    "batch": (batch_index % max_workers) + 1,
                }
            )
            done.add(name)
            queued.remove(repo)
            batch_index += 1
            progressed = True
        if not progressed:
            raise ValueError("cyclic dependency detected in repo graph")
    return {
        "ok": True,
        "max_workers": max_workers,
        "repos": len(plan_items),
        "execution_plan": plan_items,
    }


def _build_risk_report(plan: dict[str, object]) -> dict[str, object]:
    items = plan.get("execution_plan", [])
    assert isinstance(items, list)
    high = sum(1 for item in items if isinstance(item, dict) and int(item.get("priority", 100)) <= 20)
    med = sum(
        1
        for item in items
        if isinstance(item, dict) and 20 < int(item.get("priority", 100)) <= 60
    )
    low = sum(1 for item in items if isinstance(item, dict) and int(item.get("priority", 100)) > 60)
    score = max(0, 100 - (high * 10 + med * 4 + low))
    return {
        "ok": True,
        "portfolio_risk_score": score,
        "risk_buckets": {"high": high, "medium": med, "low": low},
        "recommendation": "SHIP_WITH_CONTROLS" if score >= 70 else "NO_SHIP",
    }


def _score_execution_results(results_payload: dict[str, object]) -> dict[str, object]:
    rows = results_payload.get("results", [])
    if not isinstance(rows, list):
        raise ValueError("results must be an array")
    ok = 0
    fail = 0
    error = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", ""))
        if status == "ok":
            ok += 1
        elif status == "fail":
            fail += 1
        elif status == "error":
            error += 1
    total = max(1, ok + fail + error)
    reliability = max(0, int((ok / total) * 100) - error * 5)
    return {
        "ok": True,
        "totals": {"ok": ok, "fail": fail, "error": error},
        "execution_reliability_score": reliability,
        "recommendation": "SHIP_WITH_CONTROLS" if fail == 0 and error == 0 else "NO_SHIP",
    }


def _render_portfolio_report(
    *,
    plan: dict[str, object] | None,
    risk: dict[str, object] | None,
    score: dict[str, object] | None,
) -> str:
    lines = ["# Portfolio Orchestration Report", ""]
    if plan is not None:
        lines.append(f"- Planned repositories: {int(plan.get('repos', 0))}")
        lines.append(f"- Max workers: {int(plan.get('max_workers', 0))}")
    if risk is not None:
        lines.append(f"- Portfolio risk score: {int(risk.get('portfolio_risk_score', 0))}")
        lines.append(f"- Risk recommendation: {str(risk.get('recommendation', 'UNKNOWN'))}")
    if score is not None:
        lines.append(
            f"- Execution reliability score: {int(score.get('execution_reliability_score', 0))}"
        )
        lines.append(f"- Execution recommendation: {str(score.get('recommendation', 'UNKNOWN'))}")
    lines.append("")
    lines.append("Generated by: sdetkit portfolio-orchestrate report")
    lines.append("")
    return "\n".join(lines)


def _render_portfolio_dashboard_html(
    *,
    plan: dict[str, object] | None,
    risk: dict[str, object] | None,
    score: dict[str, object] | None,
    execution: dict[str, object] | None,
    policy: dict[str, object] | None,
) -> str:
    repos = int((plan or {}).get("repos", 0))
    workers = int((plan or {}).get("max_workers", 0))
    risk_score = int((risk or {}).get("portfolio_risk_score", 0))
    reliability = int((score or {}).get("execution_reliability_score", 0))
    decision = str((policy or {}).get("decision", "UNKNOWN"))
    results = (execution or {}).get("results", [])
    rows_html = ""
    if isinstance(results, list):
        rendered = []
        for item in results:
            if not isinstance(item, dict):
                continue
            rendered.append(
                "<tr>"
                f"<td>{item.get('repo', '')}</td>"
                f"<td>{item.get('language', '')}</td>"
                f"<td>{item.get('status', '')}</td>"
                f"<td>{item.get('mode', '')}</td>"
                "</tr>"
            )
        rows_html = "\n".join(rendered)
    return f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8' />
  <title>Portfolio Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(5, minmax(140px,1fr)); gap: 12px; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; }}
    .label {{ color: #666; font-size: 12px; }}
    .value {{ font-size: 22px; font-weight: 600; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 18px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  </style>
</head>
<body>
  <h1>Portfolio Orchestration Dashboard</h1>
  <div class='grid'>
    <div class='card'><div class='label'>Repos</div><div class='value'>{repos}</div></div>
    <div class='card'><div class='label'>Workers</div><div class='value'>{workers}</div></div>
    <div class='card'><div class='label'>Risk Score</div><div class='value'>{risk_score}</div></div>
    <div class='card'><div class='label'>Reliability</div><div class='value'>{reliability}</div></div>
    <div class='card'><div class='label'>Decision</div><div class='value'>{decision}</div></div>
  </div>
  <h2>Execution Results</h2>
  <table>
    <thead><tr><th>Repo</th><th>Language</th><th>Status</th><th>Mode</th></tr></thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</body>
</html>
"""


def _load_policy(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("policy must be a JSON object")
    return payload


def _evaluate_policy(
    *,
    risk: dict[str, object],
    score: dict[str, object],
    execution: dict[str, object],
    policy: dict[str, object],
) -> dict[str, object]:
    max_risk_score = int(policy.get("max_risk_score", 35))
    min_execution_reliability = int(policy.get("min_execution_reliability", 80))
    max_failures = int(policy.get("max_failures", 0))
    allow_stopped_early = bool(policy.get("allow_stopped_early", False))
    risk_score = int(risk.get("portfolio_risk_score", 100))
    reliability = int(score.get("execution_reliability_score", 0))
    failure_count = int(execution.get("failure_count", 0))
    stopped_early = bool(execution.get("stopped_early", False))
    violations: list[str] = []
    if risk_score > max_risk_score:
        violations.append(f"risk_score {risk_score} > {max_risk_score}")
    if reliability < min_execution_reliability:
        violations.append(f"reliability {reliability} < {min_execution_reliability}")
    if failure_count > max_failures:
        violations.append(f"failure_count {failure_count} > {max_failures}")
    if stopped_early and not allow_stopped_early:
        violations.append("stopped_early is true")
    decision = "SHIP" if not violations else "NO_SHIP"
    return {
        "ok": True,
        "policy_name": str(policy.get("name", "default")),
        "decision": decision,
        "violations": violations,
        "signals": {
            "risk_score": risk_score,
            "execution_reliability_score": reliability,
            "failure_count": failure_count,
            "stopped_early": stopped_early,
        },
    }


def _analyze_plan(plan: dict[str, object]) -> dict[str, object]:
    rows = plan.get("execution_plan", [])
    if not isinstance(rows, list):
        raise ValueError("execution_plan must be an array")
    graph: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("repo", ""))
        deps = row.get("depends_on", [])
        if not name:
            continue
        graph[name] = [str(dep) for dep in deps] if isinstance(deps, list) else []

    depth_cache: dict[str, int] = {}

    def _depth(node: str, stack: set[str]) -> int:
        if node in depth_cache:
            return depth_cache[node]
        if node in stack:
            raise ValueError("cycle detected while analyzing plan")
        stack.add(node)
        deps = graph.get(node, [])
        if not deps:
            depth_cache[node] = 1
        else:
            depth_cache[node] = 1 + max(_depth(dep, stack) for dep in deps if dep in graph)
        stack.remove(node)
        return depth_cache[node]

    levels: dict[int, list[str]] = {}
    for node in graph:
        level = _depth(node, set())
        levels.setdefault(level, []).append(node)
    return {
        "ok": True,
        "repos": len(graph),
        "critical_path_length": max(levels) if levels else 0,
        "levels": {str(level): sorted(nodes) for level, nodes in sorted(levels.items())},
    }


def _adapter_command(language: str, repo_path: str) -> list[str]:
    lang = language.lower()
    if lang == "python":
        return ["python", "-m", "sdetkit", "gate", "fast", "--repo", repo_path]
    if lang == "node":
        return ["npm", "test", "--prefix", repo_path]
    if lang == "go":
        return ["go", "test", "./...", repo_path]
    return ["echo", f"no-adapter:{language}", repo_path]


def _load_adapter_registry(path: Path) -> dict[str, list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("adapter registry must be a JSON object")
    registry: dict[str, list[str]] = {}
    for language, command in payload.items():
        if not isinstance(language, str) or not isinstance(command, list):
            raise ValueError("adapter entries must map string language -> string list command")
        command_tokens = [str(token) for token in command]
        registry[language.lower()] = command_tokens
    return registry


def _adapter_command_from_registry(
    registry: dict[str, list[str]], language: str, repo_path: str
) -> list[str]:
    template = registry.get(language.lower())
    if template is None:
        return _adapter_command(language, repo_path)
    return [token.replace("{repo_path}", repo_path) for token in template]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _append_history_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _build_history_trend(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"ok": True, "runs": 0, "ship_rate": 0.0, "avg_risk_score": 0.0}
    runs = 0
    ship = 0
    risk_scores: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            continue
        runs += 1
        if str(payload.get("decision", "")) == "SHIP":
            ship += 1
        risk_scores.append(int(payload.get("risk_score", 100)))
    avg_risk = float(sum(risk_scores) / len(risk_scores)) if risk_scores else 0.0
    ship_rate = float(ship / runs) if runs else 0.0
    return {"ok": True, "runs": runs, "ship_rate": ship_rate, "avg_risk_score": avg_risk}


def _run_pipeline_bundle(
    *,
    repo_graph: Path,
    schema: Path,
    adapters: Path,
    policy_path: Path,
    max_workers: int,
    run: bool,
    timeout_seconds: int,
    retries: int,
    max_failures: int,
    history_path: Path,
    out_dir: Path,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    graph = _load_repo_graph(repo_graph)
    _validate_against_repo_schema(graph, schema)
    _validate_repo_graph_shape(graph)
    plan = _build_plan(graph, max_workers=max(1, int(max_workers)))
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    risk = _build_risk_report(plan)
    (out_dir / "risk.json").write_text(json.dumps(risk, indent=2) + "\n", encoding="utf-8")
    execution = _execute_plan(
        plan,
        max_workers=max(1, int(max_workers)),
        run=run,
        timeout_seconds=max(1, int(timeout_seconds)),
        adapter_registry=_load_adapter_registry(adapters),
        artifact_dir=out_dir / "workers",
        retries=max(0, int(retries)),
        max_failures=max(0, int(max_failures)),
    )
    (out_dir / "execution.json").write_text(json.dumps(execution, indent=2) + "\n", encoding="utf-8")
    score = _score_execution_results(execution)
    (out_dir / "score.json").write_text(json.dumps(score, indent=2) + "\n", encoding="utf-8")
    policy_eval = _evaluate_policy(
        risk=risk,
        score=score,
        execution=execution,
        policy=_load_policy(policy_path),
    )
    (out_dir / "policy.json").write_text(json.dumps(policy_eval, indent=2) + "\n", encoding="utf-8")
    _append_history_record(
        history_path,
        {
            "ts": _utc_now(),
            "decision": str(policy_eval.get("decision", "NO_SHIP")),
            "risk_score": int(risk.get("portfolio_risk_score", 100)),
            "reliability_score": int(score.get("execution_reliability_score", 0)),
            "failure_count": int(execution.get("failure_count", 0)),
        },
    )
    trend = _build_history_trend(history_path)
    (out_dir / "history-trend.json").write_text(json.dumps(trend, indent=2) + "\n", encoding="utf-8")
    analysis = _analyze_plan(plan)
    (out_dir / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    report = _render_portfolio_report(plan=plan, risk=risk, score=score)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    dashboard = _render_portfolio_dashboard_html(
        plan=plan,
        risk=risk,
        score=score,
        execution=execution,
        policy=policy_eval,
    )
    (out_dir / "dashboard.html").write_text(dashboard, encoding="utf-8")
    return {
        "decision": str(policy_eval.get("decision", "NO_SHIP")),
        "risk_score": int(risk.get("portfolio_risk_score", 100)),
        "reliability": int(score.get("execution_reliability_score", 0)),
        "failure_count": int(execution.get("failure_count", 0)),
    }


def _execute_plan(
    plan: dict[str, object],
    max_workers: int,
    *,
    run: bool = False,
    timeout_seconds: int = 120,
    adapter_registry: dict[str, list[str]] | None = None,
    artifact_dir: Path | None = None,
    retries: int = 0,
    max_failures: int = 0,
) -> dict[str, object]:
    items = plan.get("execution_plan", [])
    assert isinstance(items, list)

    def _run_item(item: dict[str, object]) -> dict[str, object]:
        repo = str(item.get("repo", "unknown"))
        language = str(item.get("language", "unknown"))
        repo_path = str(item.get("path", f"repos/{repo}"))
        command = (
            _adapter_command_from_registry(adapter_registry, language, repo_path)
            if adapter_registry is not None
            else _adapter_command(language, repo_path)
        )
        started_at = _utc_now()
        run_id = str(uuid.uuid4())
        if not run:
            return {
                "worker": f"adapter-{language.lower()}",
                "run_id": run_id,
                "repo": repo,
                "language": language,
                "status": "queued",
                "mode": "dry-run",
                "started_at": started_at,
                "finished_at": _utc_now(),
                "inputs": {"path": repo_path},
                "evidence": [],
                "result": {"returncode": 0},
                "escalation": {"required": False, "reason": ""},
                "command": command,
            }
        attempt = 0
        last_error = ""
        while attempt <= retries:
            attempt += 1
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
            except Exception as exc:  # defensive execution boundary
                last_error = str(exc)
                completed = None
            if completed is not None and completed.returncode == 0:
                return {
                    "worker": f"adapter-{language.lower()}",
                    "run_id": run_id,
                    "repo": repo,
                    "language": language,
                    "status": "ok",
                    "mode": "run",
                    "attempts": attempt,
                    "started_at": started_at,
                    "finished_at": _utc_now(),
                    "inputs": {"path": repo_path},
                    "evidence": [],
                    "result": {"returncode": int(completed.returncode)},
                    "escalation": {"required": False, "reason": ""},
                    "returncode": int(completed.returncode),
                    "command": command,
                    "stdout": completed.stdout[-500:],
                    "stderr": completed.stderr[-500:],
                }
            if completed is not None and completed.returncode != 0:
                last_error = completed.stderr[-500:] if completed.stderr else "non-zero return code"
        if completed is not None:
            return {
                "worker": f"adapter-{language.lower()}",
                "run_id": run_id,
                "repo": repo,
                "language": language,
                "status": "fail",
                "mode": "run",
                "attempts": attempt,
                "started_at": started_at,
                "finished_at": _utc_now(),
                "inputs": {"path": repo_path},
                "evidence": [],
                "result": {"returncode": int(completed.returncode)},
                "escalation": {
                    "required": True,
                    "reason": f"adapter command failed after {attempt} attempt(s)",
                },
                "returncode": int(completed.returncode),
                "command": command,
                "stdout": completed.stdout[-500:],
                "stderr": completed.stderr[-500:],
            }
        return {
            "worker": f"adapter-{language.lower()}",
            "run_id": run_id,
            "repo": repo,
            "language": language,
            "status": "error",
            "mode": "run",
            "attempts": attempt,
            "started_at": started_at,
            "finished_at": _utc_now(),
            "inputs": {"path": repo_path},
            "evidence": [],
            "result": {"returncode": 2},
            "escalation": {"required": True, "reason": f"exception during adapter execution: {last_error}"},
            "command": command,
            "error": last_error,
        }

    rows = [item for item in items if isinstance(item, dict)]
    pending = {str(item.get("repo", f"repo-{idx}")): item for idx, item in enumerate(rows)}
    completed: set[str] = set()
    results: list[dict[str, object]] = []
    failure_count = 0
    while pending:
        ready = []
        for repo, item in list(pending.items()):
            deps = item.get("depends_on", [])
            dep_list = [str(dep) for dep in deps] if isinstance(deps, list) else []
            if all(dep in completed for dep in dep_list):
                ready.append((repo, item))
        if not ready:
            raise ValueError("execute_plan blocked due to unresolved dependency cycle")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_run_item, item): repo for repo, item in ready}
            for future in as_completed(futures):
                repo = futures[future]
                result = future.result()
                results.append(result)
                if str(result.get("status")) in {"fail", "error"}:
                    failure_count += 1
                if artifact_dir is not None:
                    artifact_dir.mkdir(parents=True, exist_ok=True)
                    (artifact_dir / f"{repo}.worker.json").write_text(
                        json.dumps(result, indent=2) + "\n", encoding="utf-8"
                    )
                completed.add(repo)
                pending.pop(repo, None)
        if max_failures > 0 and failure_count >= max_failures:
            break
    return {
        "ok": True,
        "results": sorted(results, key=lambda row: str(row.get("repo"))),
        "max_workers": max_workers,
        "stopped_early": bool(max_failures > 0 and failure_count >= max_failures),
        "failure_count": failure_count,
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdetkit portfolio")
    sub = p.add_subparsers(dest="cmd", required=True)

    orchestrate = sub.add_parser("orchestrate", help="Build a multi-repo execution plan")
    orchestrate.add_argument("--repo-graph", required=True)
    orchestrate.add_argument("--schema", default="schemas/repo-graph.schema.json")
    orchestrate.add_argument("--max-workers", type=int, default=4)
    orchestrate.add_argument("--out", required=True)

    risk = sub.add_parser("risk-report", help="Generate a portfolio risk report from a plan")
    risk.add_argument("--plan", required=True)
    risk.add_argument("--out", required=True)
    execute = sub.add_parser("execute", help="Build multi-worker adapter execution intents from a plan")
    execute.add_argument("--plan", required=True)
    execute.add_argument("--max-workers", type=int, default=4)
    execute.add_argument("--run", action="store_true", help="Execute adapter commands instead of dry-run intents")
    execute.add_argument("--timeout-seconds", type=int, default=120)
    execute.add_argument("--adapters", default="config/portfolio_adapters.json")
    execute.add_argument("--artifact-dir", default="")
    execute.add_argument("--retries", type=int, default=0)
    execute.add_argument("--max-failures", type=int, default=0)
    execute.add_argument("--out", required=True)
    validate = sub.add_parser("validate-graph", help="Validate repo graph structure before orchestration")
    validate.add_argument("--repo-graph", required=True)
    validate.add_argument("--schema", default="schemas/repo-graph.schema.json")
    score = sub.add_parser(
        "score-execution",
        help="Generate reliability and ship recommendation from execution results JSON",
    )
    score.add_argument("--results", required=True)
    score.add_argument("--out", required=True)
    report = sub.add_parser("report", help="Render markdown executive report from generated artifacts")
    report.add_argument("--plan", default="")
    report.add_argument("--risk", default="")
    report.add_argument("--score", default="")
    report.add_argument("--out", required=True)
    analyze = sub.add_parser(
        "analyze-plan",
        help="Analyze dependency depth/critical-path characteristics for an execution plan",
    )
    analyze.add_argument("--plan", required=True)
    analyze.add_argument("--out", required=True)
    pipeline = sub.add_parser(
        "run-pipeline",
        help="Execute the full portfolio pipeline (validate, plan, execute, risk, score, analyze, report)",
    )
    pipeline.add_argument("--repo-graph", required=True)
    pipeline.add_argument("--schema", default="schemas/repo-graph.schema.json")
    pipeline.add_argument("--adapters", default="config/portfolio_adapters.json")
    pipeline.add_argument("--max-workers", type=int, default=4)
    pipeline.add_argument("--run", action="store_true", help="Execute adapter commands in pipeline")
    pipeline.add_argument("--timeout-seconds", type=int, default=120)
    pipeline.add_argument("--retries", type=int, default=0)
    pipeline.add_argument("--max-failures", type=int, default=0)
    pipeline.add_argument("--policy", default="config/portfolio_policy.default.json")
    pipeline.add_argument("--history", default=".sdetkit/portfolio-history.jsonl")
    pipeline.add_argument("--out-dir", required=True)
    policy = sub.add_parser(
        "evaluate-policy", help="Evaluate policy decision from risk/score/execution artifacts"
    )
    policy.add_argument("--risk", required=True)
    policy.add_argument("--score", required=True)
    policy.add_argument("--execution", required=True)
    policy.add_argument("--policy", default="config/portfolio_policy.default.json")
    policy.add_argument("--out", required=True)
    history = sub.add_parser("history-trend", help="Build trend metrics from pipeline history JSONL")
    history.add_argument("--history", default=".sdetkit/portfolio-history.jsonl")
    history.add_argument("--out", required=True)
    dashboard = sub.add_parser("dashboard", help="Render HTML dashboard from pipeline artifacts")
    dashboard.add_argument("--plan", required=True)
    dashboard.add_argument("--risk", required=True)
    dashboard.add_argument("--score", required=True)
    dashboard.add_argument("--execution", required=True)
    dashboard.add_argument("--policy", required=True)
    dashboard.add_argument("--out", required=True)
    batch = sub.add_parser("batch-run", help="Run multiple portfolio pipelines from a batch manifest")
    batch.add_argument("--manifest", required=True)
    batch.add_argument("--out-dir", required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    ns = _parser().parse_args(argv)
    if ns.cmd == "orchestrate":
        graph = _load_repo_graph(Path(ns.repo_graph))
        _validate_against_repo_schema(graph, Path(ns.schema))
        _validate_repo_graph_shape(graph)
        plan = _build_plan(graph, max_workers=max(1, int(ns.max_workers)))
        Path(ns.out).write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote execution plan: {ns.out}")
        return 0
    if ns.cmd == "execute":
        plan_payload = json.loads(Path(ns.plan).read_text(encoding="utf-8"))
        if not isinstance(plan_payload, dict):
            raise ValueError("plan must be a JSON object")
        execution = _execute_plan(
            plan_payload,
            max_workers=max(1, int(ns.max_workers)),
            run=bool(ns.run),
            timeout_seconds=max(1, int(ns.timeout_seconds)),
            adapter_registry=_load_adapter_registry(Path(ns.adapters)),
            artifact_dir=Path(ns.artifact_dir) if str(ns.artifact_dir).strip() else None,
            retries=max(0, int(ns.retries)),
            max_failures=max(0, int(ns.max_failures)),
        )
        Path(ns.out).write_text(json.dumps(execution, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote execution intents: {ns.out}")
        return 0
    if ns.cmd == "validate-graph":
        graph = _load_repo_graph(Path(ns.repo_graph))
        _validate_against_repo_schema(graph, Path(ns.schema))
        _validate_repo_graph_shape(graph)
        print("Repo graph validation: OK")
        return 0
    if ns.cmd == "score-execution":
        results_payload = json.loads(Path(ns.results).read_text(encoding="utf-8"))
        if not isinstance(results_payload, dict):
            raise ValueError("results must be a JSON object")
        score = _score_execution_results(results_payload)
        Path(ns.out).write_text(json.dumps(score, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote execution scorecard: {ns.out}")
        return 0
    if ns.cmd == "report":
        plan_payload = (
            json.loads(Path(ns.plan).read_text(encoding="utf-8"))
            if str(ns.plan).strip()
            else None
        )
        risk_payload = (
            json.loads(Path(ns.risk).read_text(encoding="utf-8"))
            if str(ns.risk).strip()
            else None
        )
        score_payload = (
            json.loads(Path(ns.score).read_text(encoding="utf-8"))
            if str(ns.score).strip()
            else None
        )
        report_md = _render_portfolio_report(
            plan=plan_payload if isinstance(plan_payload, dict) else None,
            risk=risk_payload if isinstance(risk_payload, dict) else None,
            score=score_payload if isinstance(score_payload, dict) else None,
        )
        Path(ns.out).write_text(report_md, encoding="utf-8")
        print(f"Wrote portfolio report: {ns.out}")
        return 0
    if ns.cmd == "analyze-plan":
        plan_payload = json.loads(Path(ns.plan).read_text(encoding="utf-8"))
        if not isinstance(plan_payload, dict):
            raise ValueError("plan must be a JSON object")
        analysis = _analyze_plan(plan_payload)
        Path(ns.out).write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote plan analysis: {ns.out}")
        return 0
    if ns.cmd == "run-pipeline":
        out_dir = Path(ns.out_dir)
        _run_pipeline_bundle(
            repo_graph=Path(ns.repo_graph),
            schema=Path(ns.schema),
            adapters=Path(ns.adapters),
            policy_path=Path(ns.policy),
            max_workers=max(1, int(ns.max_workers)),
            run=bool(ns.run),
            timeout_seconds=max(1, int(ns.timeout_seconds)),
            retries=max(0, int(ns.retries)),
            max_failures=max(0, int(ns.max_failures)),
            history_path=Path(ns.history),
            out_dir=out_dir,
        )
        print(f"Wrote pipeline artifacts: {out_dir}")
        return 0
    if ns.cmd == "evaluate-policy":
        risk = json.loads(Path(ns.risk).read_text(encoding="utf-8"))
        score = json.loads(Path(ns.score).read_text(encoding="utf-8"))
        execution = json.loads(Path(ns.execution).read_text(encoding="utf-8"))
        policy_payload = _load_policy(Path(ns.policy))
        if not isinstance(risk, dict) or not isinstance(score, dict) or not isinstance(execution, dict):
            raise ValueError("risk/score/execution payloads must be JSON objects")
        evaluation = _evaluate_policy(
            risk=risk,
            score=score,
            execution=execution,
            policy=policy_payload,
        )
        Path(ns.out).write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote policy decision: {ns.out}")
        return 0
    if ns.cmd == "history-trend":
        trend = _build_history_trend(Path(ns.history))
        Path(ns.out).write_text(json.dumps(trend, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote history trend: {ns.out}")
        return 0
    if ns.cmd == "dashboard":
        plan = json.loads(Path(ns.plan).read_text(encoding="utf-8"))
        risk = json.loads(Path(ns.risk).read_text(encoding="utf-8"))
        score = json.loads(Path(ns.score).read_text(encoding="utf-8"))
        execution = json.loads(Path(ns.execution).read_text(encoding="utf-8"))
        policy = json.loads(Path(ns.policy).read_text(encoding="utf-8"))
        if not all(isinstance(x, dict) for x in [plan, risk, score, execution, policy]):
            raise ValueError("dashboard inputs must be JSON objects")
        html = _render_portfolio_dashboard_html(
            plan=plan,
            risk=risk,
            score=score,
            execution=execution,
            policy=policy,
        )
        Path(ns.out).write_text(html, encoding="utf-8")
        print(f"Wrote dashboard: {ns.out}")
        return 0
    if ns.cmd == "batch-run":
        manifest = json.loads(Path(ns.manifest).read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("batch manifest must be a JSON object")
        portfolios = manifest.get("portfolios", [])
        if not isinstance(portfolios, list):
            raise ValueError("batch manifest must include array field 'portfolios'")
        out_root = Path(ns.out_dir)
        out_root.mkdir(parents=True, exist_ok=True)
        summaries: list[dict[str, object]] = []
        for item in portfolios:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", f"portfolio-{len(summaries)+1}"))
            portfolio_out = out_root / name
            summary = _run_pipeline_bundle(
                repo_graph=Path(str(item.get("repo_graph"))),
                schema=Path(str(item.get("schema", "schemas/repo-graph.schema.json"))),
                adapters=Path(str(item.get("adapters", "config/portfolio_adapters.json"))),
                policy_path=Path(str(item.get("policy", "config/portfolio_policy.default.json"))),
                max_workers=int(item.get("max_workers", 4)),
                run=bool(item.get("run", False)),
                timeout_seconds=int(item.get("timeout_seconds", 120)),
                retries=int(item.get("retries", 0)),
                max_failures=int(item.get("max_failures", 0)),
                history_path=out_root / "batch-history.jsonl",
                out_dir=portfolio_out,
            )
            summary["name"] = name
            summaries.append(summary)
        ship = sum(1 for x in summaries if str(x.get("decision")) == "SHIP")
        aggregate = {
            "ok": True,
            "portfolios": len(summaries),
            "ship": ship,
            "no_ship": len(summaries) - ship,
            "summaries": summaries,
        }
        (out_root / "batch-summary.json").write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote batch artifacts: {out_root}")
        return 0
    plan_payload = json.loads(Path(ns.plan).read_text(encoding="utf-8"))
    if not isinstance(plan_payload, dict):
        raise ValueError("plan must be a JSON object")
    report = _build_risk_report(plan_payload)
    Path(ns.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote portfolio risk report: {ns.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
