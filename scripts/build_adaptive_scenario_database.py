#!/usr/bin/env python3
"""Build adaptive scenario database from repository test and automation surfaces."""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path


def _domain_for_path(path: Path) -> str:
    p = path.as_posix()
    if "security" in p:
        return "security"
    if "release" in p or "version" in p:
        return "release"
    if "repo" in p or "policy" in p:
        return "governance"
    if "review" in p or "doctor" in p or "adaptive" in p:
        return "reliability"
    return "quality"


def _iter_test_nodes(tree: ast.AST) -> Iterable[tuple[list[str], ast.AST]]:
    class_stack: list[str] = []

    def walk(node: ast.AST) -> Iterable[tuple[list[str], ast.AST]]:
        nonlocal class_stack
        if isinstance(node, ast.ClassDef):
            class_stack.append(node.name)
            for child in node.body:
                yield from walk(child)
            class_stack.pop()
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            yield (class_stack.copy(), node)
        for child in ast.iter_child_nodes(node):
            yield from walk(child)

    yield from walk(tree)


def _parametrize_cases(node: ast.AST) -> int:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return 1
    multiplier = 1
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        func = dec.func
        if not isinstance(func, ast.Attribute) or func.attr != "parametrize":
            continue
        # Expect second positional arg with iterable of cases
        if len(dec.args) < 2:
            continue
        vals = dec.args[1]
        try:
            literal = ast.literal_eval(vals)
        except Exception:
            continue
        if isinstance(literal, (list, tuple, set)):
            case_count = len(literal)
            if case_count > 0:
                multiplier *= case_count
    return max(1, multiplier)


def _extract_test_scenarios(file: Path, repo_root: Path) -> list[dict]:
    rel = file.relative_to(repo_root).as_posix()
    text = file.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    out: list[dict] = []
    domain = _domain_for_path(file)
    for class_stack, node in _iter_test_nodes(tree):
        name = node.name
        scoped = "::".join([*class_stack, name]) if class_stack else name
        base_id = f"{rel}::{scoped}"
        case_count = _parametrize_cases(node)
        if case_count == 1:
            out.append(
                {
                    "scenario_id": base_id,
                    "domain": domain,
                    "source": rel,
                    "status": "active",
                    "kind": "test_function",
                }
            )
        else:
            for idx in range(case_count):
                out.append(
                    {
                        "scenario_id": f"{base_id}[case-{idx + 1}]",
                        "domain": domain,
                        "source": rel,
                        "status": "active",
                        "kind": "parametrized_test_case",
                    }
                )
    return out


def _extract_contract_scenarios(repo_root: Path) -> list[dict]:
    out: list[dict] = []
    for p in sorted((repo_root / "docs/contracts").glob("*.json")):
        rel = p.relative_to(repo_root).as_posix()
        out.append(
            {
                "scenario_id": f"contract::{rel}",
                "domain": "governance",
                "source": rel,
                "status": "active",
                "kind": "contract_validation",
            }
        )
    return out


def _extract_workflow_scenarios(repo_root: Path) -> list[dict]:
    out: list[dict] = []
    wf_dir = repo_root / ".github/workflows"
    for p in sorted(wf_dir.glob("*.yml")):
        rel = p.relative_to(repo_root).as_posix()
        out.append(
            {
                "scenario_id": f"workflow::{rel}",
                "domain": "reliability",
                "source": rel,
                "status": "active",
                "kind": "workflow_execution",
            }
        )
    return out


def _extract_module_scenarios(repo_root: Path) -> list[dict]:
    out: list[dict] = []
    for p in sorted((repo_root / "src/sdetkit").glob("**/*.py")):
        rel = p.relative_to(repo_root).as_posix()
        domain = _domain_for_path(p)
        out.append(
            {
                "scenario_id": f"module::{rel}",
                "domain": domain,
                "source": rel,
                "status": "active",
                "kind": "module_surface",
            }
        )
    return out


def _extract_script_scenarios(repo_root: Path) -> list[dict]:
    out: list[dict] = []
    for p in sorted((repo_root / "scripts").glob("*.py")):
        rel = p.relative_to(repo_root).as_posix()
        domain = _domain_for_path(p)
        out.append(
            {
                "scenario_id": f"script::{rel}",
                "domain": domain,
                "source": rel,
                "status": "active",
                "kind": "automation_script",
            }
        )
    return out


def _extract_docs_command_scenarios(repo_root: Path) -> list[dict]:
    out: list[dict] = []
    command_pattern = re.compile(r"python\\s+-m\\s+sdetkit\\s+([a-z0-9\\-]+)")
    for p in sorted((repo_root / "docs").glob("**/*.md")):
        rel = p.relative_to(repo_root).as_posix()
        text = p.read_text(encoding="utf-8", errors="ignore")
        commands = sorted(set(command_pattern.findall(text)))
        for cmd in commands:
            out.append(
                {
                    "scenario_id": f"docs-command::{rel}::{cmd}",
                    "domain": "reliability",
                    "source": rel,
                    "status": "active",
                    "kind": "docs_command_contract",
                }
            )
    return out


def _generate_adaptive_reviewer_matrix() -> list[dict]:
    out: list[dict] = []
    domains = ["security", "release", "governance", "reliability", "quality"]
    severities = ["low", "medium", "high", "critical"]
    reviewer_states = [
        "stable",
        "drifting",
        "contradictory",
        "noisy",
        "degraded",
        "recovering",
        "saturated",
    ]
    decision_paths = ["go", "conditional-go", "no-go"]
    phase_ids = [1, 2, 3, 4, 5, 6]
    intelligence_modes = ["reactive", "guided", "predictive"]
    for domain in domains:
        for severity in severities:
            for state in reviewer_states:
                for decision in decision_paths:
                    for phase_id in phase_ids:
                        for intelligence_mode in intelligence_modes:
                            out.append(
                                {
                                    "scenario_id": (
                                        "adaptive-reviewer::"
                                        f"phase-{phase_id}::{domain}::{severity}::{state}::"
                                        f"{decision}::{intelligence_mode}"
                                    ),
                                    "domain": domain,
                                    "source": "synthetic/adaptive-reviewer-matrix",
                                    "status": "active",
                                    "kind": "adaptive_reviewer_matrix",
                                    "phase_id": phase_id,
                                    "intelligence_mode": intelligence_mode,
                                }
                            )
    return out


def _generate_adaptive_pr_reviewer_matrix() -> list[dict]:
    out: list[dict] = []
    domains = ["security", "release", "governance", "reliability", "quality"]
    pr_risk = ["low", "medium", "high", "critical"]
    reviewer_modes = ["human-first", "agent-first", "co-pilot"]
    phase_ids = [1, 2, 3, 4, 5, 6]
    decision_paths = ["approve", "request-changes", "escalate"]
    for domain in domains:
        for risk in pr_risk:
            for mode in reviewer_modes:
                for phase_id in phase_ids:
                    for decision in decision_paths:
                        out.append(
                            {
                                "scenario_id": (
                                    "adaptive-pr-reviewer::"
                                    f"phase-{phase_id}::{domain}::{risk}::{mode}::{decision}"
                                ),
                                "domain": domain,
                                "source": "synthetic/adaptive-pr-reviewer-matrix",
                                "status": "active",
                                "kind": "adaptive_pr_reviewer_matrix",
                                "phase_id": phase_id,
                                "reviewer_mode": mode,
                            }
                        )
    return out


def _extract_reviewer_agent_scenarios(repo_root: Path) -> list[dict]:
    out: list[dict] = []
    for p in sorted((repo_root / "templates/automations").glob("*.yaml")):
        rel = p.relative_to(repo_root).as_posix()
        stem = p.stem
        if "worker" in stem or "review" in stem or "radar" in stem:
            out.append(
                {
                    "scenario_id": f"reviewer-agent::{rel}",
                    "domain": "reliability",
                    "source": rel,
                    "status": "active",
                    "kind": "reviewer_agent_handoff",
                }
            )
    return out


def _extract_mistake_learning_scenarios(repo_root: Path) -> list[dict]:
    out: list[dict] = []
    artifacts_root = repo_root / "docs/artifacts"
    if not artifacts_root.exists():
        return out

    def _domain_for_signal(signal: str) -> str:
        lowered = signal.lower()
        if "security" in lowered:
            return "security"
        if "release" in lowered or "ship" in lowered:
            return "release"
        if "policy" in lowered or "governance" in lowered:
            return "governance"
        if "doctor" in lowered or "review" in lowered or "adaptive" in lowered:
            return "reliability"
        return "quality"

    def _append_event(*, source: str, signal: str, context: str = "") -> None:
        normalized = re.sub(r"[^a-z0-9]+", "-", signal.lower()).strip("-")
        if not normalized:
            return
        out.append(
            {
                "scenario_id": f"mistake-event::{source}::{normalized}",
                "domain": _domain_for_signal(signal),
                "source": source,
                "status": "active",
                "kind": "mistake_learning_event",
                "signal": signal,
                "context": context,
            }
        )

    for p in sorted(artifacts_root.glob("**/*.json")):
        rel = p.relative_to(repo_root).as_posix()
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        failed_steps = payload.get("failed_steps", [])
        if isinstance(failed_steps, list):
            for step in failed_steps:
                if isinstance(step, str):
                    _append_event(source=rel, signal=f"failed_step:{step}")

        failed_check_ids = payload.get("failed_check_ids", [])
        if isinstance(failed_check_ids, list):
            for check in failed_check_ids:
                if isinstance(check, str):
                    _append_event(source=rel, signal=f"failed_check:{check}")

        summary = payload.get("summary", {})
        if isinstance(summary, dict):
            failed_required = summary.get("failed_required")
            if isinstance(failed_required, int) and failed_required > 0:
                _append_event(
                    source=rel,
                    signal="failed_required_checks",
                    context=f"count={failed_required}",
                )
            failed_warn = summary.get("failed_warn")
            if isinstance(failed_warn, int) and failed_warn > 0:
                _append_event(
                    source=rel,
                    signal="warning_checks_present",
                    context=f"count={failed_warn}",
                )

        doctor = payload.get("doctor", {})
        if isinstance(doctor, dict):
            doctor_failed = doctor.get("failed_check_ids", [])
            if isinstance(doctor_failed, list):
                for check in doctor_failed:
                    if isinstance(check, str):
                        _append_event(source=rel, signal=f"doctor_failed:{check}")

        checks = payload.get("checks", [])
        if isinstance(checks, list):
            for row in checks:
                if not isinstance(row, dict):
                    continue
                passed = row.get("passed")
                check_name = row.get("check")
                if passed is False and isinstance(check_name, str):
                    _append_event(source=rel, signal=f"check_failed:{check_name}")

    if not out:
        out.append(
            {
                "scenario_id": "mistake-event::bootstrap::no_failure_signals_yet",
                "domain": "quality",
                "source": "docs/artifacts",
                "status": "active",
                "kind": "mistake_learning_event",
                "signal": "bootstrap:no_failure_signals_yet",
                "context": "No failure artifacts discovered yet; collector bootstrapped.",
            }
        )

    dedup: dict[str, dict] = {}
    for row in out:
        dedup[row["scenario_id"]] = row
    return sorted(dedup.values(), key=lambda r: str(r["scenario_id"]))


def _extract_pr_outcome_feedback_scenarios(repo_root: Path) -> list[dict]:
    out: list[dict] = []
    artifacts_root = repo_root / "docs/artifacts"
    if not artifacts_root.exists():
        return out

    for p in sorted(artifacts_root.glob("**/*.json")):
        rel = p.relative_to(repo_root).as_posix()
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        status = payload.get("status")
        if isinstance(status, str):
            out.append(
                {
                    "scenario_id": f"pr-outcome::{rel}::status::{status}",
                    "domain": "reliability",
                    "source": rel,
                    "status": "active",
                    "kind": "pr_outcome_feedback",
                    "feedback_type": "status",
                    "feedback_value": status,
                }
            )
        ok = payload.get("ok")
        if isinstance(ok, bool):
            out.append(
                {
                    "scenario_id": f"pr-outcome::{rel}::ok::{str(ok).lower()}",
                    "domain": "release",
                    "source": rel,
                    "status": "active",
                    "kind": "pr_outcome_feedback",
                    "feedback_type": "ok",
                    "feedback_value": str(ok).lower(),
                }
            )

        summary = payload.get("summary")
        if isinstance(summary, dict):
            band = summary.get("confidence_band")
            if isinstance(band, str):
                out.append(
                    {
                        "scenario_id": f"pr-outcome::{rel}::confidence_band::{band}",
                        "domain": "reliability",
                        "source": rel,
                        "status": "active",
                        "kind": "pr_outcome_feedback",
                        "feedback_type": "confidence_band",
                        "feedback_value": band,
                    }
                )
            failed_required = summary.get("failed_required")
            if isinstance(failed_required, int):
                bucket = "none" if failed_required == 0 else "required-failures"
                out.append(
                    {
                        "scenario_id": f"pr-outcome::{rel}::required::{bucket}",
                        "domain": "release",
                        "source": rel,
                        "status": "active",
                        "kind": "pr_outcome_feedback",
                        "feedback_type": "required_outcome",
                        "feedback_value": bucket,
                    }
                )

        routing = payload.get("confidence_guidance", {})
        if isinstance(routing, dict):
            route = routing.get("routing")
            if isinstance(route, str):
                out.append(
                    {
                        "scenario_id": f"pr-outcome::{rel}::routing::{route}",
                        "domain": "governance",
                        "source": rel,
                        "status": "active",
                        "kind": "pr_outcome_feedback",
                        "feedback_type": "routing",
                        "feedback_value": route,
                    }
                )

    dedup: dict[str, dict] = {}
    for row in out:
        dedup[row["scenario_id"]] = row
    return sorted(dedup.values(), key=lambda r: str(r["scenario_id"]))


def build_db(repo_root: Path) -> dict:
    tests_root = repo_root / "tests"
    scenario_entries: list[dict] = []

    for file in sorted(tests_root.rglob("test_*.py")):
        scenario_entries.extend(_extract_test_scenarios(file, repo_root))

    scenario_entries.extend(_extract_contract_scenarios(repo_root))
    scenario_entries.extend(_extract_workflow_scenarios(repo_root))
    scenario_entries.extend(_extract_module_scenarios(repo_root))
    scenario_entries.extend(_extract_script_scenarios(repo_root))
    scenario_entries.extend(_extract_docs_command_scenarios(repo_root))
    scenario_entries.extend(_generate_adaptive_reviewer_matrix())
    scenario_entries.extend(_generate_adaptive_pr_reviewer_matrix())
    scenario_entries.extend(_extract_reviewer_agent_scenarios(repo_root))
    scenario_entries.extend(_extract_mistake_learning_scenarios(repo_root))
    scenario_entries.extend(_extract_pr_outcome_feedback_scenarios(repo_root))

    dedup: dict[str, dict] = {}
    for row in scenario_entries:
        dedup[row["scenario_id"]] = row
    scenario_entries = sorted(dedup.values(), key=lambda r: str(r["scenario_id"]))

    domain_counts: Counter[str] = Counter(entry["domain"] for entry in scenario_entries)
    kind_counts: Counter[str] = Counter(entry.get("kind", "unknown") for entry in scenario_entries)
    pr_feedback = int(kind_counts.get("pr_outcome_feedback", 0))
    mistake_events = int(kind_counts.get("mistake_learning_event", 0))
    learning_signal_total = pr_feedback + mistake_events
    learning_coverage_score = int(round(min(100.0, (learning_signal_total / 20.0) * 100.0)))

    payload = {
        "schema_version": "sdetkit.adaptive-scenario-database.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "summary": {
            "total_scenarios": len(scenario_entries),
            "domains": dict(sorted(domain_counts.items())),
            "kinds": dict(sorted(kind_counts.items())),
            "target_minimum": 3000,
            "meets_target": len(scenario_entries) >= 3000,
            "adaptive_learning": {
                "pr_outcome_feedback": pr_feedback,
                "mistake_learning_event": mistake_events,
                "learning_signal_total": learning_signal_total,
                "learning_coverage_score": learning_coverage_score,
                "precision_ready": pr_feedback >= 5 and mistake_events >= 5,
            },
        },
        "scenarios": scenario_entries,
    }
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    repo_root = Path(args.repo).resolve()
    payload = build_db(repo_root)
    if args.out:
        out = Path(args.out)
    else:
        date_tag = datetime.now(UTC).date().isoformat()
        out = repo_root / "docs/artifacts" / f"adaptive-scenario-database-{date_tag}.json"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
