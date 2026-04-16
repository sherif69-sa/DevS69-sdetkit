#!/usr/bin/env python3
"""Build adaptive scenario database from repository test and automation surfaces."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable


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
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
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
                        "scenario_id": f"{base_id}[case-{idx+1}]",
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


def build_db(repo_root: Path) -> dict:
    tests_root = repo_root / "tests"
    scenario_entries: list[dict] = []

    for file in sorted(tests_root.rglob("test_*.py")):
        scenario_entries.extend(_extract_test_scenarios(file, repo_root))

    scenario_entries.extend(_extract_contract_scenarios(repo_root))
    scenario_entries.extend(_extract_workflow_scenarios(repo_root))

    domain_counts: Counter[str] = Counter(entry["domain"] for entry in scenario_entries)
    kind_counts: Counter[str] = Counter(entry.get("kind", "unknown") for entry in scenario_entries)

    payload = {
        "schema_version": "sdetkit.adaptive-scenario-database.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_scenarios": len(scenario_entries),
            "domains": dict(sorted(domain_counts.items())),
            "kinds": dict(sorted(kind_counts.items())),
            "target_minimum": 500,
            "meets_target": len(scenario_entries) >= 500,
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
        date_tag = datetime.now(timezone.utc).date().isoformat()
        out = repo_root / "docs/artifacts" / f"adaptive-scenario-database-{date_tag}.json"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
