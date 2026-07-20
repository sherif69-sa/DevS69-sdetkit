from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from sdetkit import adaptive_diagnosis, adaptive_failure_bundle
from sdetkit.boost import build_scan
from sdetkit.failure_vector_cpp import extract_cpp_failure_vector, looks_like_cpp_failure
from sdetkit.index import IGNORED_DIRS
from sdetkit.investigation_evidence import build_investigation_evidence

FAILURE_SCHEMA_VERSION = "sdetkit.investigate.failure.v1"
REPO_SCHEMA_VERSION = "sdetkit.investigate.repo.v1"
SURFACE_SCHEMA_VERSION = "sdetkit.investigate.surface.v1"
PYTHON_SOURCE_DIRS = {"src", "sdetkit"}


def _read_log(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _first_text(source: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _first_list(source: dict[str, Any], *keys: str) -> list[str]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            items = [str(item) for item in value if str(item).strip()]
            if items:
                return items
    return []


def _failure_memory_lookup_key(first: dict[str, Any], classification: str) -> str:
    explicit = _first_text(first, "memory_lookup_key")
    if explicit:
        return explicit
    signal = _first_text(first, "learning_signal")
    if signal:
        return f"diagnosis:{classification}:{signal}"
    return f"diagnosis:{classification}"


def _cpp_payload_for_failure(log_text: str) -> dict[str, Any]:
    result = extract_cpp_failure_vector(
        log_text,
        check="investigate_failure",
        environment="local_saved_evidence",
    )
    vector = result.vector
    failure_class = vector.failure_class or "unknown"
    classification = (
        f"CPP_{failure_class.upper()}_FAILURE"
        if failure_class != "unknown"
        else "CPP_FAILURE_REVIEW_REQUIRED"
    )
    proof_commands = [vector.local_repro_command] if vector.local_repro_command else []
    vector_payload = result.to_dict()
    summary = (
        vector.actual_failure
        or vector.first_failing_line
        or "Saved C++ failure evidence requires review."
    )
    return {
        "schema_version": FAILURE_SCHEMA_VERSION,
        "ok": True,
        "diagnostic_only": True,
        "automation_allowed": False,
        "command": "investigate failure",
        "classification": classification,
        "confidence": result.confidence,
        "safe_to_auto_fix": False,
        "requires_human_review": True,
        "summary": summary,
        "why_it_matters": (
            "Saved C++ compiler, linker, or test evidence was normalized without "
            "executing target code."
        ),
        "next_actions": [
            "Review the affected C++ files and saved diagnostic before proposing a change.",
            "Run the observed focused proof command only in a trusted target environment."
            if proof_commands
            else "Identify the repository-owned C++ proof command before rerunning.",
        ],
        "proof_commands": proof_commands,
        "memory_lookup_key": f"diagnosis:{classification}:cpp",
        "ecosystem": "cpp",
        "failure_vector": vector_payload,
        "diagnosis": {
            "diagnosis_count": 1,
            "source": "failure_vector_cpp",
            "diagnoses": [
                {
                    "code": classification,
                    "confidence": result.confidence,
                    "summary": summary,
                }
            ],
            "fix_plan": [
                {
                    "safe_to_auto_fix": False,
                    "requires_human_review": True,
                }
            ],
        },
    }


def _payload_for_failure(log_text: str) -> dict[str, Any]:
    if looks_like_cpp_failure(log_text):
        return _cpp_payload_for_failure(log_text)
    diagnosis_payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    diagnoses = diagnosis_payload.get("diagnoses", [])
    first = diagnoses[0] if diagnoses and isinstance(diagnoses[0], dict) else {}

    fix_plan = diagnosis_payload.get("fix_plan", [])
    first_plan = fix_plan[0] if fix_plan and isinstance(fix_plan[0], dict) else {}

    classification = str(first.get("code", "UNKNOWN_REVIEW_REQUIRED"))

    return {
        "schema_version": FAILURE_SCHEMA_VERSION,
        "ok": True,
        "diagnostic_only": True,
        "automation_allowed": False,
        "command": "investigate failure",
        "classification": classification,
        "confidence": str(first.get("confidence", "medium")),
        "safe_to_auto_fix": bool(first_plan.get("safe_to_auto_fix", False)),
        "requires_human_review": bool(first_plan.get("requires_human_review", True)),
        "summary": _first_text(first, "summary", "title", "diagnosis"),
        "why_it_matters": _first_text(
            first, "why_it_matters", "why_developers_miss_it", "risk_if_ignored"
        ),
        "next_actions": _first_list(first, "next_actions", "recommended_fix"),
        "proof_commands": _first_list(first, "proof_commands"),
        "memory_lookup_key": _failure_memory_lookup_key(first, classification),
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
        return (
            f"{name} is a production surface without an obvious matching test file in the summary."
        )
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


def _surface_text_match(surface: str, rel: str, text: str) -> bool:
    normalized = surface.lower().replace("-", "_")
    path_token = rel.lower().replace("-", "_")
    if normalized in path_token:
        return True
    return normalized in text.lower().replace("-", "_")


def _surface_files(root: Path, surface: str) -> tuple[list[str], list[str]]:
    production_files: list[str] = []
    test_files: list[str] = []
    for path in _iter_repo_files(root):
        rel = _rel(root, path)
        if not rel.endswith(".py"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if not _surface_text_match(surface, rel, text):
            continue
        if _is_source_file(rel):
            production_files.append(rel)
        elif _is_test_file(rel):
            test_files.append(rel)
    return sorted(production_files), sorted(test_files)


def _public_symbols_for_file(root: Path, rel: str) -> list[dict[str, str]]:
    path = root / rel
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return []
    symbols: list[dict[str, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith(
            "_"
        ):
            symbols.append({"symbol": node.name, "kind": "function", "file": rel})
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            symbols.append({"symbol": node.name, "kind": "class", "file": rel})
            for child in node.body:
                if isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and not child.name.startswith("_"):
                    symbols.append(
                        {"symbol": f"{node.name}.{child.name}", "kind": "method", "file": rel}
                    )
    return symbols


def _public_symbols(root: Path, production_files: list[str]) -> list[str]:
    rows: list[dict[str, str]] = []
    for rel in production_files:
        rows.extend(_public_symbols_for_file(root, rel))
    return [row["symbol"] for row in sorted(rows, key=lambda r: (r["file"], r["symbol"]))]


def _method_groups(symbols: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    sync_methods: dict[str, str] = {}
    async_methods: dict[str, str] = {}
    for symbol in symbols:
        if "." not in symbol:
            continue
        class_name, method = symbol.split(".", 1)
        if "Async" in class_name:
            async_methods[method] = symbol
        else:
            sync_methods[method] = symbol
    return sync_methods, async_methods


def _parity_risks(symbols: list[str]) -> list[dict[str, str]]:
    sync_methods, async_methods = _method_groups(symbols)
    risks: list[dict[str, str]] = []
    if not sync_methods or not async_methods:
        return risks
    for method, sync_symbol in sorted(sync_methods.items()):
        if method not in async_methods:
            risks.append(
                {
                    "kind": "sync_async_method_gap",
                    "sync_symbol": sync_symbol,
                    "async_symbol": method,
                    "status": "missing",
                }
            )
    return risks


def _payload_for_surface(root: str, surface: str) -> dict[str, Any]:
    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise OSError(f"repository root does not exist: {root}")
    clean_surface = surface.strip()
    if not clean_surface:
        raise OSError("surface name is required")
    production_files, test_files = _surface_files(root_path, clean_surface)
    symbols = _public_symbols(root_path, production_files)
    risks = _parity_risks(symbols)
    return {
        "schema_version": SURFACE_SCHEMA_VERSION,
        "ok": True,
        "diagnostic_only": True,
        "automation_allowed": False,
        "command": "investigate surface",
        "root": root_path.as_posix(),
        "surface": clean_surface,
        "production_files": production_files,
        "test_files": test_files,
        "public_symbols": symbols,
        "parity_risks": risks,
        "recommended_probe": "write focused parity repro"
        if risks
        else "review focused surface tests",
    }


def _failure_bundle_handoff(bundle: dict[str, Any]) -> dict[str, Any]:
    artifacts = bundle.get("artifacts", {})
    artifacts_map = artifacts if isinstance(artifacts, dict) else {}
    return {
        "schema_version": str(bundle.get("schema_version", "")),
        "bundle_path": str(bundle.get("bundle_path", "")),
        "status": str(bundle.get("status", "unknown")),
        "primary_diagnosis_code": str(bundle.get("primary_diagnosis_code", "") or ""),
        "diagnosis_count": int(bundle.get("diagnosis_count", 0) or 0),
        "review_first": bool(bundle.get("review_first", False)),
        "safe_to_auto_fix": bool(bundle.get("safe_to_auto_fix", False)),
        "artifacts": artifacts_map,
    }


def _attach_failure_bundle_handoff(
    payload: dict[str, Any],
    *,
    log_path: str | Path,
    out_dir: str | Path | None,
) -> dict[str, Any]:
    if not out_dir:
        return payload

    diagnosis = payload.get("diagnosis", {})
    diagnosis_count = 0
    if isinstance(diagnosis, dict):
        diagnosis_count = int(diagnosis.get("diagnosis_count", 0) or 0)

    bundle = adaptive_failure_bundle.build_failure_bundle(
        log_path=Path(log_path),
        out_dir=Path(out_dir),
        proof_failed=bool(diagnosis_count),
    )
    updated = dict(payload)
    updated["failure_bundle"] = _failure_bundle_handoff(bundle)
    return updated


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

    bundle = payload.get("failure_bundle")
    if isinstance(bundle, dict):
        lines.extend(
            [
                "",
                "## Failure intelligence bundle",
                f"- bundle path: `{bundle.get('bundle_path', '')}`",
                f"- status: **{bundle.get('status', 'unknown')}**",
                f"- primary diagnosis: **{bundle.get('primary_diagnosis_code', '') or 'none'}**",
                f"- diagnosis count: **{bundle.get('diagnosis_count', 0)}**",
                f"- review first: **{bundle.get('review_first', False)}**",
                f"- safe to auto-fix: **{bundle.get('safe_to_auto_fix', False)}**",
            ]
        )
        artifacts = bundle.get("artifacts", {})
        if isinstance(artifacts, dict) and artifacts.get("operator_brief_markdown"):
            lines.append(f"- operator brief: `{artifacts['operator_brief_markdown']}`")

    return "\n".join(lines).rstrip() + "\n"


def render_repo_markdown(payload: dict[str, Any]) -> str:
    shape = payload.get("repo_shape", {}) if isinstance(payload.get("repo_shape"), dict) else {}
    surfaces = (
        payload.get("top_surfaces", []) if isinstance(payload.get("top_surfaces"), list) else []
    )
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


def render_surface_markdown(payload: dict[str, Any]) -> str:
    prod = payload.get("production_files", [])
    tests = payload.get("test_files", [])
    symbols = payload.get("public_symbols", [])
    risks = payload.get("parity_risks", [])
    lines = [
        "# Surface investigation",
        "",
        f"- surface: **{payload.get('surface', '')}**",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- production files: **{len(prod) if isinstance(prod, list) else 0}**",
        f"- test files: **{len(tests) if isinstance(tests, list) else 0}**",
        f"- parity risks: **{len(risks) if isinstance(risks, list) else 0}**",
        "",
        "## Public symbols",
        "",
    ]
    if symbols:
        for symbol in symbols[:20]:
            lines.append(f"- `{symbol}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Parity risks", ""])
    if risks:
        lines.extend(["| Kind | Sync symbol | Async symbol | Status |", "|---|---|---|---|"])
        for risk in risks:
            lines.append(
                "| {kind} | `{sync}` | `{async_}` | {status} |".format(
                    kind=risk.get("kind", ""),
                    sync=risk.get("sync_symbol", ""),
                    async_=risk.get("async_symbol", ""),
                    status=risk.get("status", ""),
                )
            )
    else:
        lines.append("No parity risks were detected in this focused scan.")
    lines.extend(["", "## Recommended probe", "", str(payload.get("recommended_probe", ""))])
    return "\n".join(lines).rstrip() + "\n"


def render_evidence_markdown(payload: dict[str, Any]) -> str:
    files = payload.get("files", {}) if isinstance(payload.get("files"), dict) else {}
    lines = [
        "# Investigation evidence",
        "",
        f"- classification: **{payload.get('classification', '')}**",
        f"- surface: **{payload.get('surface', '')}**",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- proof status: **{payload.get('proof_status', '')}**",
        "",
        "## Generated files",
        "",
    ]
    for key in sorted(files):
        lines.append(f"- {key}: `{files[key]}`")
    proof = payload.get("proof_commands", [])
    if proof:
        lines.extend(["", "## Proof commands", "", "```bash"])
        lines.extend(str(command) for command in proof)
        lines.append("```")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit investigate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    failure = sub.add_parser("failure", help="Classify a failure log with adaptive diagnosis")
    failure.add_argument("--log", required=True, help="Path to a text log to investigate")
    failure.add_argument("--format", choices=["json", "markdown"], default="json")
    failure.add_argument("--out", default="", help="Optional output file")
    failure.add_argument(
        "--failure-bundle-out-dir",
        default="",
        help="Optional directory for a full adaptive failure intelligence bundle.",
    )

    repo = sub.add_parser("repo", help="Summarize repository investigation surfaces")
    repo.add_argument("--root", default=".", help="Repository root to investigate")
    repo.add_argument("--format", choices=["json", "markdown"], default="json")
    repo.add_argument("--out", default="", help="Optional output file")

    surface = sub.add_parser("surface", help="Summarize one focused repository surface")
    surface.add_argument("--root", default=".", help="Repository root to investigate")
    surface.add_argument("--surface", required=True, help="Surface name to investigate")
    surface.add_argument("--format", choices=["json", "markdown"], default="json")
    surface.add_argument("--out", default="", help="Optional output file")

    evidence = sub.add_parser("evidence", help="Write investigation candidate evidence artifacts")
    evidence.add_argument("--classification", required=True, help="Diagnosis classification")
    evidence.add_argument("--surface", required=True, help="Surface name for the evidence bundle")
    evidence.add_argument("--out-dir", required=True, help="Directory for generated evidence")
    evidence.add_argument("--root", default=".", help="Repository root for context")
    evidence.add_argument("--format", choices=["json", "markdown"], default="json")
    evidence.add_argument("--out", default="", help="Optional output file")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "failure":
            log_text = _read_log(args.log)
            payload = _attach_failure_bundle_handoff(
                _payload_for_failure(log_text),
                log_path=args.log,
                out_dir=args.failure_bundle_out_dir or None,
            )
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
        elif args.cmd == "surface":
            payload = _payload_for_surface(args.root, args.surface)
            rendered = (
                json.dumps(payload, indent=2, sort_keys=True) + "\n"
                if args.format == "json"
                else render_surface_markdown(payload)
            )
        elif args.cmd == "evidence":
            payload = build_investigation_evidence(
                args.classification,
                args.surface,
                args.out_dir,
                root=args.root,
            )
            rendered = (
                json.dumps(payload, indent=2, sort_keys=True) + "\n"
                if args.format == "json"
                else render_evidence_markdown(payload)
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
