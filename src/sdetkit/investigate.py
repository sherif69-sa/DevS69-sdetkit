from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from sdetkit import adaptive_diagnosis
from sdetkit.boost import build_scan
from sdetkit.index import IGNORED_DIRS

FAILURE_SCHEMA_VERSION = "sdetkit.investigate.failure.v1"
REPO_SCHEMA_VERSION = "sdetkit.investigate.repo.v1"
PYTHON_SOURCE_DIRS = {"src", "sdetkit"}


def _read_log(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _payload_for_failure(log_text: str) -> dict[str, Any]:
    diagnosis_payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    diagnoses = diagnosis_payload.get("diagnoses", [])
    first = diagnoses[0] if diagnoses and isinstance(diagnoses[0], dict) else {}

    fix_plan = diagnosis_payload.get("fix_plan", [])
    first_plan = fix_plan[0] if fix_plan and isinstance(fix_plan[0], dict) else {}

    return {
        "schema_version": FAILURE_SCHEMA_VERSION,
        "ok": True,
        "diagnostic_only": True,
        "automation_allowed": False,
        "command": "investigate failure",
        "classification": str(first.get("code", "UNKNOWN_REVIEW_REQUIRED")),
        "confidence": str(first.get("confidence", "medium")),
        "safe_to_auto_fix": bool(first_plan.get("safe_to_auto_fix", False)),
        "requires_human_review": bool(first_plan.get("requires_human_review", True)),
        "summary": str(first.get("summary", "")),
        "why_it_matters": str(first.get("why_it_matters", "")),
        "next_actions": list(first.get("next_actions", []))
        if isinstance(first.get("next_actions"), list)
        else [],
        "proof_commands": list(first.get("proof_commands", []))
        if isinstance(first.get("proof_commands"), list)
        else [],
        "memory_lookup_key": str(first.get("memory_lookup_key", "")),
        "diagnosis": diagnosis_payload,
    }


def _iter_repo_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in __import__("os").walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        base = Path(current)
        if any(part in IGNORED_DIRS for part in base.relative_to(root).parts):
            continue
        for name in sorted(names):
            files.append(base / name)
    return files


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_source_file(rel: str) -> bool:
    parts = rel.split("/")
    return rel.endswith(".py") and bool(parts) and parts[0] in PYTHON_SOURCE_DIRS


def _is_test_file(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1] if parts else rel
    return rel.endswith(".py") and ("tests" in parts or name.startswith("test_"))


def _is_workflow_file(rel: str) -> bool:
    return rel.startswith(".github/workflows/") and rel.endswith((".yml", ".yaml"))


def _surface_name_from_source(rel: str) -> str:
    stem = Path(rel).stem
    if stem == "__init__":
        parent = Path(rel).parent.name
        return parent or stem
    return stem


def _surface_name_from_test(rel: str) -> str:
    stem = Path(rel).stem
    if stem.startswith("test_"):
        return stem[5:]
    if stem.endswith("_test"):
        return stem[:-5]
    return stem


def _first_values(values: list[str], limit: int = 5) -> list[str]:
    return list(dict.fromkeys(values))[:limit]


def _repo_shape_from_scan(scan: dict[str, Any], files: list[Path], root: Path) -> dict[str, int]:
    signals = scan.get("signals", {}) if isinstance(scan.get("signals", {}), dict) else {}
    source_files = int(signals.get("source_file_count", 0) or 0)
    test_files = int(signals.get("test_file_count", 0) or 0)
    workflow_files = int(signals.get("workflow_count", 0) or 0)
    if source_files or test_files or workflow_files:
        return {
            "source_files": source_files,
            "test_files": test_files,
            "workflow_files": workflow_files,
        }
    rels = [_rel(root, path) for path in files]
    return {
        "source_files": sum(1 for rel in rels if _is_source_file(rel)),
        "test_files": sum(1 for rel in rels if _is_test_file(rel)),
        "workflow_files": sum(1 for rel in rels if _is_workflow_file(rel)),
    }


def _surface_reason(name: str, prod: list[str], tests: list[str]) -> str:
    if prod and tests:
        return f"{name} has production and test coverage signals for focused investigation."
    if prod:
        return f"{name} is a production surface without an obvious matching test file in the summary."
    return f"{name} appears in tests and may point to a behavior surface worth narrowing."


def _top_surfaces(root: Path, files: list[Path]) -> list[dict[str, Any]]:
    production_by_surface: dict[str, list[str]] = defaultdict(list)
    tests_by_surface: dict[str, list[str]] = defaultdict(list)
    for path in files:
        rel = _rel(root, path)
        if _is_source_file(rel):
            production_by_surface[_surface_name_from_source(rel)].append(rel)
        elif _is_test_file(rel):
            tests_by_surface[_surface_name_from_test(rel)].append(rel)

    names = sorted(set(production_by_surface) | set(tests_by_surface))
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for name in names:
        prod = sorted(production_by_surface.get(name, []))
        tests = sorted(tests_by_surface.get(name, []))
        score = len(prod) * 3 + len(tests) * 2 + (5 if prod and tests else 0)
        item = {
            "name": name,
            "production_files": _first_values(prod),
            "test_files": _first_values(tests),
            "reason": _surface_reason(name, prod, tests),
            "recommended_next_probe": f"investigate surface --surface {name}",
        }
        scored.append((-score, name, item))
    return [item for _, _, item in sorted(scored)[:8]]


def _payload_for_repo(root: str) -> dict[str, Any]:
    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise OSError(f"repository root does not exist: {root}")
    scan = build_scan(root_path, minutes=1, max_lines=100)
    files = _iter_repo_files(root_path)
    return {
        "schema_version": REPO_SCHEMA_VERSION,
        "ok": True,
        "diagnostic_only": True,
        "automation_allowed": False,
        "command": "investigate repo",
        "root": root_path.as_posix(),
        "repo_shape": _repo_shape_from_scan(scan, files, root_path),
        "top_surfaces": _top_surfaces(root_path, files),
        "source_engines": ["boost", "index-style repo scan"],
        "recommended_next_command": "python -m sdetkit investigate surface --root . --surface <surface>",
        "boost_summary": {
            "decision": scan.get("decision"),
            "score": scan.get("score"),
            "summary": scan.get("summary"),
            "high_signal_files": scan.get("high_signal_files", []),
        },
    }


def render_failure_markdown(payload: dict[str, Any]) -> str:
    proof = payload.get("proof_commands", [])
    actions = payload.get("next_actions", [])
    lines = [
        "# Failure investigation",
        "",
        f"- classification: **{payload.get('classification', 'UNKNOWN_REVIEW_REQUIRED')}**",
        f"- confidence: **{payload.get('confidence', 'medium')}**",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- safe to auto-fix: **{payload.get('safe_to_auto_fix', False)}**",
        f"- requires human review: **{payload.get('requires_human_review', True)}**",
        "",
        "## Summary",
        "",
        str(payload.get("summary", "") or "No summary was available."),
        "",
        "## Why it matters",
        "",
        str(payload.get("why_it_matters", "") or "No additional context was available."),
    ]

    if actions:
        lines.extend(["", "## Next actions", ""])
        for action in actions:
            lines.append(f"- {action}")

    if proof:
        lines.extend(["", "## Proof commands", ""])
        lines.append("```bash")
        for command in proof:
            lines.append(str(command))
        lines.append("```")

    key = str(payload.get("memory_lookup_key", "")).strip()
    if key:
        lines.extend(["", "## Memory lookup key", "", f"`{key}`"])

    return "\n".join(lines).rstrip() + "\n"


def render_repo_markdown(payload: dict[str, Any]) -> str:
    shape = payload.get("repo_shape", {}) if isinstance(payload.get("repo_shape"), dict) else {}
    surfaces = payload.get("top_surfaces", []) if isinstance(payload.get("top_surfaces"), list) else []
    lines = [
        "# Repository investigation",
        "",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- source files: **{shape.get('source_files', 0)}**",
        f"- test files: **{shape.get('test_files', 0)}**",
        f"- workflow files: **{shape.get('workflow_files', 0)}**",
        "",
        "## Top surfaces",
        "",
        "| Surface | Production files | Test files | Next probe |",
        "|---|---:|---:|---|",
    ]
    if surfaces:
        for surface in surfaces:
            prod = surface.get("production_files", [])
            tests = surface.get("test_files", [])
            lines.append(
                "| {name} | {prod_count} | {test_count} | `{probe}` |".format(
                    name=surface.get("name", ""),
                    prod_count=len(prod) if isinstance(prod, list) else 0,
                    test_count=len(tests) if isinstance(tests, list) else 0,
                    probe=surface.get("recommended_next_probe", ""),
                )
            )
    else:
        lines.append("| none | 0 | 0 | `review repository shape manually` |")

    lines.extend(
        [
            "",
            "## What to do next",
            "",
            f"`{payload.get('recommended_next_command', '')}`",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit investigate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    failure = sub.add_parser("failure", help="Classify a failure log with adaptive diagnosis")
    failure.add_argument("--log", required=True, help="Path to a text log to investigate")
    failure.add_argument("--format", choices=["json", "markdown"], default="json")
    failure.add_argument("--out", default="", help="Optional output file")

    repo = sub.add_parser("repo", help="Summarize repository investigation surfaces")
    repo.add_argument("--root", default=".", help="Repository root to investigate")
    repo.add_argument("--format", choices=["json", "markdown"], default="json")
    repo.add_argument("--out", default="", help="Optional output file")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "failure":
            payload = _payload_for_failure(_read_log(args.log))
            rendered = (
                json.dumps(payload, indent=2, sort_keys=True) + "\n"
                if args.format == "json"
                else render_failure_markdown(payload)
            )
        elif args.cmd == "repo":
            payload = _payload_for_repo(args.root)
            rendered = (
                json.dumps(payload, indent=2, sort_keys=True) + "\n"
                if args.format == "json"
                else render_repo_markdown(payload)
            )
        else:
            return 2
    except OSError as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2

    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
