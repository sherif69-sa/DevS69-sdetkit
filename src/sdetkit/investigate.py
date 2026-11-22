from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sdetkit import adaptive_diagnosis, adaptive_failure_bundle
from sdetkit.boost import build_scan
from sdetkit.failure_vector_adapters import (
    FailureVectorAdapterResult,
    diagnosis_code,
    extract_ecosystem_failure_vector,
)
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


_ECOSYSTEM_LABELS = {
    "cpp": "C++",
    "dotnet": ".NET",
    "go": "Go",
    "java": "Java",
    "javascript_typescript": "JavaScript/TypeScript",
    "rust": "Rust",
}


def _ecosystem_payload_for_failure(
    log_text: str, result: FailureVectorAdapterResult
) -> dict[str, Any]:
    vector = result.vector
    ecosystem = result.ecosystem
    label = _ECOSYSTEM_LABELS.get(ecosystem, ecosystem)
    classification = diagnosis_code(result)
    proof_commands = [vector.local_repro_command] if vector.local_repro_command else []
    summary = (
        vector.actual_failure
        or vector.first_failing_line
        or f"Saved {label} failure evidence requires review."
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
            f"Saved {label} {result.tool} evidence was normalized without executing target code."
        ),
        "next_actions": [
            f"Review the affected {label} files and saved diagnostic before proposing a change.",
            "Run the observed focused proof command only in a trusted target environment."
            if proof_commands
            else f"Identify the repository-owned {label} proof command before rerunning.",
        ],
        "proof_commands": proof_commands,
        "memory_lookup_key": f"diagnosis:{classification}:{ecosystem}",
        "ecosystem": ecosystem,
        "failure_vector": result.to_dict(),
        "diagnosis": {
            "diagnosis_count": 1,
            "source": "failure_vector_cpp" if ecosystem == "cpp" else "failure_vector_adapters",
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
    vector_result = extract_ecosystem_failure_vector(
        log_text, check="investigate_failure", environment="local_saved_evidence"
    )
    if vector_result.ecosystem in _ECOSYSTEM_LABELS:
        return _ecosystem_payload_for_failure(log_text, vector_result)
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
        "ecosystem": vector_result.ecosystem,
        "failure_vector": vector_result.to_dict(),
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


# =============================================================================
# Frontier 20: Deterministic Operational Advisor & Prescription Engine
# =============================================================================

ADVISE_SCHEMA_VERSION = "1.0"

CATEGORY_CONCURRENCY_RACE = "CONCURRENCY_RACE"
CATEGORY_UNMOCKED_CLOCK_FLAKE = "UNMOCKED_CLOCK_FLAKE"
CATEGORY_TEST_TAMPERING_DETECTED = "TEST_TAMPERING_DETECTED"
CATEGORY_DESTRUCTIVE_MIGRATION = "DESTRUCTIVE_MIGRATION"
CATEGORY_CONFIG_PARITY_GAP = "CONFIG_PARITY_GAP"
CATEGORY_BREAKING_CONTRACT_CHANGE = "BREAKING_CONTRACT_CHANGE"
CATEGORY_ASSERTION_BLIND_SPOT = "ASSERTION_BLIND_SPOT"
CATEGORY_LATENCY_REGRESSION = "LATENCY_REGRESSION"
CATEGORY_SUPPLY_CHAIN_POLICY_VIOLATION = "SUPPLY_CHAIN_POLICY_VIOLATION"
CATEGORY_ENV_POLLUTION = "ENV_POLLUTION"

SEVERITY_WEIGHTS: dict[str, float] = {
    "BLOCKER": 100.0,
    "HIGH": 75.0,
    "MEDIUM": 50.0,
    "LOW": 25.0,
}


def _classify_log_issue(
    log_text: str,
) -> tuple[str, str, float, str, str, str]:
    """Deterministically map a failure log into an operational category."""
    lower = log_text.lower()

    if any(
        k in lower
        for k in (
            "deadlock",
            "thread",
            "concurrency",
            "socket.timeout",
            "connection refused",
            "econnreset",
        )
    ):
        return (
            CATEGORY_CONCURRENCY_RACE,
            "BLOCKER",
            0.94,
            "Thread deadlock, unmanaged socket collision, or race condition detected in execution log",
            "Wrap shared state in synchronization primitives or bind sockets to ephemeral port 0.",
            "sdetkit chaos --iterations 10",
        )

    if any(
        k in lower
        for k in (
            "datetime.now",
            "time.sleep",
            "timestamp",
            "clock",
            "freeze_time",
            "sleepy",
        )
    ):
        return (
            CATEGORY_UNMOCKED_CLOCK_FLAKE,
            "BLOCKER",
            0.96,
            "Unmocked wall-clock query or arbitrary sleep causing timing drift and assertion race",
            "Inject frozen clock fixture or pass explicit timestamp parameter.",
            "sdetkit auto-fix --rule freeze-clock",
        )

    if any(
        k in lower
        for k in (
            "no such column",
            "table already exists",
            "destructive migration",
            "syntax error in sql",
        )
    ):
        return (
            CATEGORY_DESTRUCTIVE_MIGRATION,
            "BLOCKER",
            0.97,
            "Destructive SQL migration or breaking schema modification detected",
            "Apply expand-contract migration pattern; deprecate columns before dropping.",
            "sdetkit doctor --ops-validity",
        )

    if any(
        k in lower
        for k in (
            "keyerror",
            "missing environment",
            "environ",
            "getenv",
            "secret",
        )
    ):
        return (
            CATEGORY_CONFIG_PARITY_GAP,
            "BLOCKER",
            0.93,
            "Missing environment variable or configuration parity gap between code and deploy templates",
            "Add missing environment variable key to .env.example or deployment manifests.",
            "sdetkit doctor",
        )

    if any(k in lower for k in ("assertionerror", "mutant", "unasserted")):
        return (
            CATEGORY_ASSERTION_BLIND_SPOT,
            "HIGH",
            0.89,
            "Assertion failure or untested branch condition",
            "Strengthen test assertions to verify return state and side effects.",
            "sdetkit verify mutation",
        )

    return (
        CATEGORY_ASSERTION_BLIND_SPOT,
        "HIGH",
        0.85,
        "Test failure occurred without matching known anti-pattern signature",
        "Inspect test traceback and assert expected invariants.",
        "sdetkit investigate failure",
    )


def run_operational_advisor(
    root: Path,
    *,
    target: str | Path | None = None,
    log_path: str | Path | None = None,
    blast_radius: float | None = None,
) -> dict[str, Any]:
    """Execute deterministic operational advisor and emit ranked prescriptive action cards."""
    resolved_root = root.resolve()
    raw_suggestions: list[dict[str, Any]] = []

    # 1. Inspect log_path if provided
    if log_path:
        lp = Path(log_path)
        if not lp.is_absolute():
            lp = resolved_root / lp
        if lp.is_file():
            try:
                log_content = lp.read_text(encoding="utf-8", errors="replace")
                cat, sev, conf, ev, act, cmd = _classify_log_issue(log_content)
                rel_loc = str(
                    lp.relative_to(resolved_root) if lp.is_relative_to(resolved_root) else lp.name
                )
                raw_suggestions.append(
                    {
                        "category": cat,
                        "severity": sev,
                        "confidence": conf,
                        "location": rel_loc,
                        "evidence": ev,
                        "recommended_action": act,
                        "exact_command": cmd,
                    }
                )
            except OSError:
                # Log file unreadable or deleted; continue with other signal inspections.
                pass

    # 2. Inspect target or tests for AST smells
    tests_to_check: list[Path] = []
    if target:
        tp = Path(target)
        if not tp.is_absolute():
            tp = resolved_root / tp
        if tp.is_file():
            tests_to_check.append(tp)
        elif tp.is_dir():
            tests_to_check.extend(sorted(tp.rglob("test_*.py"))[:10])
    else:
        td = resolved_root / "tests"
        if td.is_dir():
            tests_to_check.extend(sorted(td.rglob("test_*.py"))[:15])

    for tpath in tests_to_check:
        try:
            rel_t = str(tpath.relative_to(resolved_root)).replace("\\", "/")
        except ValueError:
            rel_t = tpath.name

        try:
            from .dependency_map import inspect_test_cache_smells

            has_smell, smells = inspect_test_cache_smells(tpath)
            if has_smell:
                for smell in smells:
                    if "ENV_POLLUTION" in smell:
                        raw_suggestions.append(
                            {
                                "category": CATEGORY_ENV_POLLUTION,
                                "severity": "HIGH",
                                "confidence": 0.94,
                                "location": rel_t,
                                "evidence": smell,
                                "recommended_action": "Use pytest monkeypatch fixture to isolate environment mutations.",
                                "exact_command": f"sdetkit auto-fix --target {rel_t} --rule isolate-env",
                            }
                        )
                    elif "CLOCK_SMELL" in smell:
                        raw_suggestions.append(
                            {
                                "category": CATEGORY_UNMOCKED_CLOCK_FLAKE,
                                "severity": "HIGH",
                                "confidence": 0.95,
                                "location": rel_t,
                                "evidence": smell,
                                "recommended_action": "Inject frozen clock fixture or pass explicit timestamp parameter.",
                                "exact_command": f"sdetkit auto-fix --target {rel_t} --rule freeze-clock",
                            }
                        )
                    elif "NETWORK_SMELL" in smell:
                        raw_suggestions.append(
                            {
                                "category": CATEGORY_CONCURRENCY_RACE,
                                "severity": "HIGH",
                                "confidence": 0.91,
                                "location": rel_t,
                                "evidence": smell,
                                "recommended_action": "Bind sockets to ephemeral port 0 or use mock network fixtures.",
                                "exact_command": f"sdetkit auto-fix --target {rel_t} --rule ephemeral-port",
                            }
                        )
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            # Fallback if AST inspection fails on non-standard syntax; skip test.
            pass

    # 3. Inspect Quarantine manifest
    q_file = resolved_root / ".sdetkit" / "quarantine.json"
    if q_file.is_file():
        try:
            q_data = json.loads(q_file.read_text(encoding="utf-8"))
            records = q_data.get("records") or q_data.get("tests", {})
            if isinstance(records, dict) and records:
                expired_cnt = sum(
                    1
                    for e in records.values()
                    if isinstance(e, dict)
                    and (e.get("status") == "expired" or e.get("ttl_days") == 0)
                )
                if expired_cnt > 0:
                    raw_suggestions.append(
                        {
                            "category": CATEGORY_TEST_TAMPERING_DETECTED,
                            "severity": "MEDIUM",
                            "confidence": 0.88,
                            "location": ".sdetkit/quarantine.json",
                            "evidence": f"{expired_cnt} test(s) in quarantine have expired TTLs",
                            "recommended_action": "Audit quarantine manifest and graduate stable tests or renew quarantine TTLs.",
                            "exact_command": "sdetkit quarantine audit --prune-zombies",
                        }
                    )
                else:
                    raw_suggestions.append(
                        {
                            "category": CATEGORY_CONCURRENCY_RACE,
                            "severity": "LOW",
                            "confidence": 0.85,
                            "location": ".sdetkit/quarantine.json",
                            "evidence": f"{len(records)} test(s) are actively isolated in quarantine",
                            "recommended_action": "Run shadow test verification to evaluate flake stabilization.",
                            "exact_command": "sdetkit quarantine shadow",
                        }
                    )
        except (json.JSONDecodeError, OSError):
            # Quarantine manifest unreadable or malformed; skip quarantine signal.
            pass

    # 4. Rank suggestions by Impact Score: (severity_weight * 0.5) + (confidence * 30.0) + (br_weight * 20.0)
    br_val = blast_radius if blast_radius is not None else 20.0
    br_weight = min(100.0, max(0.0, br_val)) / 100.0

    ranked_suggestions: list[dict[str, Any]] = []
    for item in raw_suggestions:
        sev = str(item.get("severity", "LOW"))
        conf = float(item.get("confidence", 0.5))
        sev_wt = SEVERITY_WEIGHTS.get(sev, 25.0)
        impact = round((sev_wt * 0.5) + (conf * 30.0) + (br_weight * 20.0), 1)

        ranked_suggestions.append(
            {
                "rank": 0,
                "category": item["category"],
                "severity": sev,
                "confidence": round(conf, 2),
                "location": item["location"],
                "evidence": item["evidence"],
                "recommended_action": item["recommended_action"],
                "exact_command": item["exact_command"],
                "impact_score": impact,
            }
        )

    # Sort descending by impact_score, then confidence
    ranked_suggestions.sort(
        key=lambda s: (float(s["impact_score"]), float(s["confidence"])), reverse=True
    )

    for i, s in enumerate(ranked_suggestions, start=1):
        s["rank"] = i

    highest_sev = ranked_suggestions[0]["severity"] if ranked_suggestions else "LOW"
    if any(s["severity"] == "BLOCKER" for s in ranked_suggestions):
        verdict = "NO_SHIP"
    elif ranked_suggestions:
        verdict = "REVIEW"
    else:
        verdict = "SHIP"

    return {
        "schema_version": ADVISE_SCHEMA_VERSION,
        "verdict": verdict,
        "mode": "OFFLINE_DETERMINISTIC",
        "total_suggestions": len(ranked_suggestions),
        "highest_severity": highest_sev,
        "suggestions": ranked_suggestions,
    }


def render_advisor_markdown(report: dict[str, Any]) -> str:
    """Render structured Markdown action cards from advisor report."""
    verdict = report.get("verdict", "SHIP")
    total = report.get("total_suggestions", 0)
    sev = report.get("highest_severity", "LOW")
    suggestions = report.get("suggestions", [])

    lines = [
        f"# [ADVISE: {verdict}] SDETKit Deterministic Operational Advisor",
        "",
        f"- **Verdict**: **{verdict}**",
        "- **Execution Mode**: `OFFLINE_DETERMINISTIC` (Zero AI, Zero Network)",
        f"- **Prescriptions**: `{total} action cards` (Highest Severity: `{sev}`)",
        "",
    ]

    if not suggestions:
        lines.append(
            "No operational defects or quality regressions detected. Repository is release ready.\n"
        )
        return "\n".join(lines)

    lines.append("### Prescriptive Action Cards\n")
    for s in suggestions:
        rk = s.get("rank", 1)
        cat = s.get("category", "ISSUE")
        sv = s.get("severity", "LOW")
        conf = float(s.get("confidence", 1.0)) * 100.0
        loc = s.get("location", "unknown")
        ev = s.get("evidence", "")
        act = s.get("recommended_action", "")
        cmd = s.get("exact_command", "")

        lines.extend(
            [
                f"#### #{rk} [{sv} ({conf:.1f}%)] {cat}",
                f"- **Location**: `{loc}`",
                f"- **Evidence**: {ev}",
                f"- **Recommended Action**: {act}",
                "- **Exact Remediation Command**:",
                "```bash",
                f"{cmd}",
                "```",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def render_advisor_text(report: dict[str, Any]) -> str:
    """Render concise plain-text summary of advisor findings."""
    verdict = report.get("verdict", "SHIP")
    total = report.get("total_suggestions", 0)
    sev = report.get("highest_severity", "LOW")
    suggestions = report.get("suggestions", [])

    lines = [
        f"SDETKit Operational Advisor: verdict={verdict} suggestions={total} highest_severity={sev}",
    ]
    for s in suggestions:
        lines.append(
            f"  #{s.get('rank')}: [{s.get('severity')}] {s.get('category')} at {s.get('location')} -> {s.get('exact_command')}"
        )
    return "\n".join(lines) + "\n"


def advise_main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for sdetkit advise."""
    parser = argparse.ArgumentParser(
        prog="sdetkit advise",
        description="Deterministic operational advisor and prescriptive action engine",
    )
    parser.add_argument(
        "--repo-root",
        "--root",
        "-r",
        dest="repo_root",
        default=".",
        help="Repository root directory",
    )
    parser.add_argument("--target", default=None, help="Target test file or directory to diagnose")
    parser.add_argument("--log", default=None, help="Path to failure log or traceback file")
    parser.add_argument(
        "--blast-radius",
        type=float,
        default=None,
        help="Candidate blast radius override (0-100)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "md", "markdown"],
        default="md",
        help="Output format (default: md)",
    )
    parser.add_argument("--out", default=None, help="Write output to file")
    parser.add_argument("--summary-out", default=None, help="Append markdown summary to file")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    root = Path(args.repo_root).resolve()

    report = run_operational_advisor(
        root=root,
        target=args.target,
        log_path=args.log,
        blast_radius=args.blast_radius,
    )

    if args.format == "json":
        output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    elif args.format == "text":
        output = render_advisor_text(report)
    else:
        output = render_advisor_markdown(report)

    if args.out:
        out_p = Path(args.out).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(output, encoding="utf-8")

    if args.summary_out:
        sm_p = Path(args.summary_out).resolve()
        sm_p.parent.mkdir(parents=True, exist_ok=True)
        with sm_p.open("a", encoding="utf-8") as sf:
            sf.write(render_advisor_markdown(report))

    sys.stdout.write(output)
    return 0 if report.get("verdict") in ("SHIP", "REVIEW") else 1


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
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == "advise":
        return advise_main(raw_args[1:])
    if os.environ.get("SDETKIT_SUBCOMMAND") == "advise":
        return advise_main(raw_args)
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
