from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .evidence_workspace import record_workspace_run
from .inspect_compare import run_compare
from .inspect_data import run_inspect
from .judgment import build_judgment, load_latest_previous_payload
from .review_engine import (
    build_contradiction_graph,
    decide_escalation,
    decide_stop,
    investigation_confidence,
    rank_likely_issue_tracks,
)
from .security import SecurityError, safe_path

SCHEMA_VERSION = "sdetkit.inspect.project.v1"
EXIT_OK = 0
EXIT_FINDINGS = 2


def _safe_slug(value: str) -> str:
    out: list[str] = []
    for ch in value.lower():
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "inspect-project"


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"inspect-project: expected JSON object at {path}")
    return loaded


def _validate_policy(payload: dict[str, Any]) -> str | None:
    allowed = {"inputs", "rules", "compare", "precedence", "outputs"}
    unknown = sorted(k for k in payload if k not in allowed)
    if unknown:
        return "inspect-project: unknown policy section(s): " + ", ".join(repr(k) for k in unknown)

    inputs = payload.get("inputs", {})
    if not isinstance(inputs, dict):
        return "inspect-project: inputs must be an object"
    scopes = inputs.get("scopes", [])
    if not isinstance(scopes, list) or not scopes:
        return "inspect-project: inputs.scopes must be a non-empty array"
    for idx, scope in enumerate(scopes):
        if not isinstance(scope, dict):
            return f"inspect-project: inputs.scopes[{idx}] must be an object"
        name = str(scope.get("name", "")).strip()
        if not name:
            return f"inspect-project: inputs.scopes[{idx}].name is required"
        include = scope.get("include", [])
        if not isinstance(include, list) or not include:
            return f"inspect-project: inputs.scopes[{idx}].include must be a non-empty array"

    rules = payload.get("rules", {})
    if not isinstance(rules, dict):
        return "inspect-project: rules must be an object"
    source_count = int("rules_file" in rules) + int("inline" in rules)
    if source_count > 1:
        return "inspect-project: rules may define only one source: rules_file or inline"

    compare = payload.get("compare", {})
    if not isinstance(compare, dict):
        return "inspect-project: compare must be an object"
    baseline = compare.get("baseline", "latest_vs_previous")
    if str(baseline) not in {"latest_vs_previous", "none"}:
        return "inspect-project: compare.baseline must be 'latest_vs_previous' or 'none'"
    thresholds = compare.get("thresholds", {})
    if thresholds is not None and not isinstance(thresholds, dict):
        return "inspect-project: compare.thresholds must be an object"

    precedence = payload.get("precedence", {})
    if precedence is not None and not isinstance(precedence, dict):
        return "inspect-project: precedence must be an object"

    outputs = payload.get("outputs", {})
    if outputs is not None and not isinstance(outputs, dict):
        return "inspect-project: outputs must be an object"
    if isinstance(outputs, dict):
        for key in ("project_subdir", "scope_dir"):
            value = outputs.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                return f"inspect-project: outputs.{key} must be a non-empty string when provided"
    return None


def _resolve_rules_payload(project_dir: Path, policy: dict[str, Any]) -> dict[str, Any]:
    rules_cfg = policy.get("rules", {})
    if not isinstance(rules_cfg, dict):
        return {}
    if "inline" in rules_cfg:
        inline = rules_cfg.get("inline")
        if not isinstance(inline, dict):
            raise ValueError("inspect-project: rules.inline must be an object")
        return inline
    if "rules_file" in rules_cfg:
        rules_file = project_dir / str(rules_cfg.get("rules_file", ""))
        if not rules_file.exists():
            raise ValueError(f"inspect-project: rules file not found: {rules_file}")
        return _load_json(rules_file)
    return {}


def _materialize_scope(
    project_dir: Path, scope: dict[str, Any], run_root: Path
) -> tuple[list[Path], Path]:
    include_patterns = sorted(str(p) for p in scope.get("include", []) if str(p).strip())
    if not include_patterns:
        raise ValueError(
            f"inspect-project: scope {scope.get('name', 'unknown')!r} has no include patterns"
        )
    discovered: set[Path] = set()
    for pattern in include_patterns:
        for candidate in project_dir.glob(pattern):
            if candidate.is_file() and candidate.suffix.lower() in {".csv", ".json"}:
                discovered.add(candidate.resolve())
    files = sorted(discovered, key=lambda p: p.as_posix())
    if not files:
        raise ValueError(f"inspect-project: scope {scope['name']!r} matched no supported files")

    scope_root_name = str(scope.get("_scope_dir_name", "scopes"))
    scope_dir = run_root / scope_root_name / _safe_slug(str(scope["name"])) / "input"
    scope_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str]] = []
    for src in files:
        rel = src.relative_to(project_dir)
        dst = scope_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        manifest_rows.append(
            {"source": rel.as_posix(), "copied_to": dst.relative_to(run_root).as_posix()}
        )
    (scope_dir / "scope-input-manifest.json").write_text(
        json.dumps({"scope": scope["name"], "files": manifest_rows}, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return files, scope_dir


def _threshold_failures(
    compare_summary: dict[str, Any], thresholds: dict[str, Any]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for key in sorted(thresholds):
        limit = int(thresholds.get(key, 0))
        actual = int(compare_summary.get(key, 0))
        if actual > limit:
            failures.append(
                {
                    "kind": "compare_threshold",
                    "metric": key,
                    "actual": actual,
                    "threshold": limit,
                    "priority": 20,
                }
            )
    return failures


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"SDETKit inspect-project: {'PASS' if payload['ok'] else 'FAIL'}",
        f"project_dir: {payload['project_dir']}",
        f"scopes: {payload['summary']['scopes']}",
        f"inspect_fail_scopes: {payload['summary']['inspect_fail_scopes']}",
        f"compare_fail_scopes: {payload['summary']['compare_fail_scopes']}",
        "top_findings:",
    ]
    for item in payload.get("findings", [])[:20]:
        lines.append(
            f"- {item['scope']} [{item['kind']}] priority={item['priority']} "
            f"message={item['message']}"
        )
    judgment = payload.get("judgment", {})
    if isinstance(judgment, dict):
        lines.append(
            f"judgment: status={judgment.get('status')} severity={judgment.get('severity')} confidence={judgment.get('confidence', {}).get('score')}"
        )
        contradictions = judgment.get("contradictions", [])
        if isinstance(contradictions, list) and contradictions:
            lines.append(f"judgment_contradictions: {len(contradictions)}")
    lines.append("")
    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit inspect-project",
        description="Run reusable project inspection policy packs over dataset families.",
    )
    p.add_argument("project_dir", help="Directory containing evidence and policy pack")
    p.add_argument(
        "--policy", default="inspect-project.json", help="Policy JSON file relative to project_dir"
    )
    p.add_argument(
        "--workspace-root", default=".sdetkit/workspace", help="Shared evidence workspace root"
    )
    p.add_argument(
        "--out-dir",
        default=None,
        help="Project output directory (default .sdetkit/inspect-project/<project-name>)",
    )
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--no-workspace", action="store_true", help="Disable shared workspace recording")
    return p


def inspect_project_main(argv: Sequence[str] | None = None) -> int:
    ns = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    try:
        project_dir = safe_path(Path.cwd(), ns.project_dir, allow_absolute=True).resolve()
        workspace_root = safe_path(Path.cwd(), ns.workspace_root, allow_absolute=True)
    except SecurityError as exc:
        sys.stderr.write(f"inspect-project: path rejected: {exc}\n")
        return EXIT_FINDINGS
    if not project_dir.exists() or not project_dir.is_dir():
        sys.stderr.write(
            f"inspect-project: project_dir does not exist or is not a directory: {project_dir}\n"
        )
        return EXIT_FINDINGS

    policy_path = project_dir / ns.policy
    if not policy_path.exists():
        sys.stderr.write(f"inspect-project: policy file not found: {policy_path}\n")
        return EXIT_FINDINGS

    try:
        policy = _load_json(policy_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(str(exc) + "\n")
        return EXIT_FINDINGS

    error = _validate_policy(policy)
    if error:
        sys.stderr.write(error + "\n")
        return EXIT_FINDINGS

    if ns.out_dir:
        try:
            out_dir = safe_path(Path.cwd(), ns.out_dir, allow_absolute=True)
        except SecurityError as exc:
            sys.stderr.write(f"inspect-project: out-dir rejected: {exc}\n")
            return EXIT_FINDINGS
    else:
        out_dir = Path(".sdetkit") / "inspect-project" / _safe_slug(project_dir.name)
    outputs_cfg = policy.get("outputs", {}) if isinstance(policy.get("outputs"), dict) else {}
    project_subdir = str(outputs_cfg.get("project_subdir", "")).strip()
    scope_dir_name = str(outputs_cfg.get("scope_dir", "scopes")).strip() or "scopes"
    run_root = out_dir / _safe_slug(project_subdir) if project_subdir else out_dir
    run_root.mkdir(parents=True, exist_ok=True)

    try:
        rules_payload = _resolve_rules_payload(project_dir, policy)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return EXIT_FINDINGS

    inputs = policy.get("inputs", {})
    scopes = sorted(inputs.get("scopes", []), key=lambda item: str(item.get("name", "")))

    inspect_runs: list[dict[str, Any]] = []
    compare_runs: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    compare_cfg = policy.get("compare", {}) if isinstance(policy.get("compare"), dict) else {}
    thresholds = (
        compare_cfg.get("thresholds", {}) if isinstance(compare_cfg.get("thresholds"), dict) else {}
    )
    baseline_mode = str(compare_cfg.get("baseline", "latest_vs_previous"))
    precedence_cfg = (
        policy.get("precedence", {}) if isinstance(policy.get("precedence"), dict) else {}
    )
    weights_cfg = (
        precedence_cfg.get("weights", {}) if isinstance(precedence_cfg.get("weights"), dict) else {}
    )

    for scope in scopes:
        scope = dict(scope)
        scope["_scope_dir_name"] = scope_dir_name
        scope_name = str(scope.get("name"))
        scope_slug = _safe_slug(scope_name)
        try:
            matched_files, scope_input_dir = _materialize_scope(project_dir, scope, run_root)
        except ValueError as exc:
            findings.append(
                {
                    "scope": scope_name,
                    "kind": "input_matching",
                    "priority": 30,
                    "message": str(exc),
                }
            )
            continue

        inspect_out = run_root / scope_dir_name / scope_slug / "inspect"
        try:
            inspect_rc, inspect_payload, inspect_json_path, inspect_txt_path = run_inspect(
                input_path=scope_input_dir,
                out_dir=inspect_out,
                rules_payload=rules_payload,
                workspace_root=workspace_root,
                record_workspace=not ns.no_workspace,
                workspace_scope=scope_slug,
            )
        except ValueError as exc:
            findings.append(
                {
                    "scope": scope_name,
                    "kind": "inspect_execution",
                    "priority": 30,
                    "message": str(exc),
                }
            )
            continue

        inspect_runs.append(
            {
                "scope": scope_name,
                "scope_slug": scope_slug,
                "matched_files": [p.relative_to(project_dir).as_posix() for p in matched_files],
                "inspect_ok": inspect_payload["ok"],
                "inspect_run_hash": inspect_payload.get("workspace", {}).get("run_hash"),
                "inspect_artifacts": {
                    "inspect_json": inspect_json_path.relative_to(run_root).as_posix(),
                    "inspect_txt": inspect_txt_path.relative_to(run_root).as_posix(),
                },
            }
        )
        if inspect_rc != EXIT_OK:
            findings.append(
                {
                    "scope": scope_name,
                    "kind": "inspect_findings",
                    "priority": 25,
                    "message": "inspect reported findings for this scope",
                }
            )

        if baseline_mode != "latest_vs_previous":
            continue

        compare_out = run_root / scope_dir_name / scope_slug / "compare"
        compare_scope = f"inspect-project:{project_dir.name}:{scope_slug}"
        try:
            current_record = Path(inspect_payload.get("workspace", {}).get("record_path", ""))
            if ns.no_workspace or not current_record:
                continue
            current_record_abs = workspace_root / current_record
            manifest = _load_json(workspace_root / "manifest.json")
            runs = [
                item
                for item in manifest.get("runs", [])
                if isinstance(item, dict)
                and str(item.get("workflow", "")) == "inspect"
                and str(item.get("scope", "")) == scope_slug
            ]
            runs_sorted = sorted(
                runs,
                key=lambda item: (int(item.get("run_order", 0)), str(item.get("run_hash", ""))),
            )
            previous = None
            current_hash = str(inspect_payload.get("workspace", {}).get("run_hash", ""))
            for item in runs_sorted:
                if str(item.get("run_hash", "")) == current_hash:
                    break
                previous = item
            if previous is None:
                continue
            left_record = workspace_root / str(previous.get("record_path", ""))
            left_payload = _load_json(left_record).get("payload")
            right_payload = _load_json(current_record_abs).get("payload")
            if not isinstance(left_payload, dict) or not isinstance(right_payload, dict):
                continue
            compare_rc, compare_payload, compare_json, compare_txt = run_compare(
                left_payload=left_payload,
                right_payload=right_payload,
                left_label=f"workspace:{left_record.as_posix()}",
                right_label=f"workspace:{current_record_abs.as_posix()}",
                out_dir=compare_out,
                out_scope=compare_scope,
                workspace_root=workspace_root,
                record_workspace=not ns.no_workspace,
            )
            compare_runs.append(
                {
                    "scope": scope_name,
                    "compare_ok": compare_payload["ok"],
                    "summary": compare_payload.get("summary", {}),
                    "compare_run_hash": compare_payload.get("workspace", {}).get("run_hash"),
                    "compare_artifacts": {
                        "inspect_compare_json": compare_json.relative_to(run_root).as_posix(),
                        "inspect_compare_txt": compare_txt.relative_to(run_root).as_posix(),
                    },
                }
            )
            if compare_rc != EXIT_OK:
                findings.append(
                    {
                        "scope": scope_name,
                        "kind": "compare_drift",
                        "priority": 15,
                        "message": "compare detected drift against previous run",
                    }
                )
            for failure in _threshold_failures(compare_payload.get("summary", {}), thresholds):
                findings.append(
                    {
                        "scope": scope_name,
                        "kind": failure["kind"],
                        "priority": int(failure["priority"]),
                        "message": (
                            f"{failure['metric']}={failure['actual']} exceeds threshold={failure['threshold']}"
                        ),
                    }
                )
        except (OSError, ValueError, json.JSONDecodeError):
            findings.append(
                {
                    "scope": scope_name,
                    "kind": "compare_execution",
                    "priority": 20,
                    "message": "compare execution failed for this scope",
                }
            )

    ordered_findings = sorted(
        [
            {
                **item,
                "priority": int(
                    weights_cfg.get(str(item.get("kind", "")), int(item.get("priority", 0)))
                ),
            }
            for item in findings
        ],
        key=lambda item: (
            int(item.get("priority", 0)),
            str(item.get("kind", "")),
            str(item.get("scope", "")),
            str(item.get("message", "")),
        ),
    )

    inspect_fail_scopes = len(
        {f["scope"] for f in ordered_findings if f["kind"].startswith("inspect")}
    )
    compare_fail_scopes = len(
        {f["scope"] for f in ordered_findings if f["kind"].startswith("compare")}
    )
    contradiction_inputs: list[dict[str, Any]] = []
    if inspect_fail_scopes > 0:
        contradiction_inputs.append({"kind": "inspect"})
    if compare_fail_scopes > 0:
        contradiction_inputs.append({"kind": "compare"})
    conflicting_evidence = build_contradiction_graph(
        findings=contradiction_inputs,
        detection={"repo_like": compare_fail_scopes > 0},
        doctor_kind="inspect",
        inspect_kind="compare",
    )
    if inspect_fail_scopes == 0 and compare_fail_scopes > 0 and not conflicting_evidence:
        conflicting_evidence.append(
            {
                "id": "inspect-project:compare-without-inspect-failures",
                "kind": "cross_surface_disagreement",
                "message": "Inspect scope checks passed while compare drift still failed.",
            }
        )
    finding_items = [
        {
            "id": f"inspect-project:{idx + 1}",
            "kind": str(item.get("kind", "finding")),
            "severity": "high" if str(item.get("kind", "")).startswith("compare") else "medium",
            "priority": min(70, 100 - int(item.get("priority", 0)) * 2),
            "why_it_matters": str(item.get("message", "")),
            "next_action": str(item.get("message", "")),
            "message": str(item.get("message", "")),
        }
        for idx, item in enumerate(ordered_findings[:10])
    ]
    supporting_evidence = [
        {"kind": "inspect_scope", "scope": row.get("scope"), "ok": row.get("inspect_ok")}
        for row in inspect_runs
    ]

    previous_payload, _ = (None, None)
    previous_summary = None
    stability = 0.7
    if not ns.no_workspace:
        previous_payload, _ = load_latest_previous_payload(
            workspace_root=workspace_root,
            workflow="inspect-project",
            scope=_safe_slug(project_dir.name),
        )
    if isinstance(previous_payload, dict):
        prev_findings = int(previous_payload.get("summary", {}).get("total_findings", 0))
        cur_findings = len(ordered_findings)
        if cur_findings > prev_findings:
            stability = 0.35
            previous_summary = "regressing"
        elif cur_findings < prev_findings:
            stability = 0.85
            previous_summary = "improving"
        else:
            pass

    project_ok = len(ordered_findings) == 0
    blocking = compare_fail_scopes > 0
    judgment = build_judgment(
        workflow="inspect-project",
        findings=finding_items,
        supporting_evidence=supporting_evidence,
        conflicting_evidence=conflicting_evidence,
        completeness=1.0 if scopes else 0.4,
        stability=stability,
        previous_summary=previous_summary,
        workflow_ok=project_ok,
        blocking=blocking,
    )
    adaptive_confidence = investigation_confidence(
        source_workflows=[{"workflow": "inspect", "status": "ok"} for _ in inspect_runs]
        + [{"workflow": "inspect-compare", "status": "ok"} for _ in compare_runs],
        findings=finding_items,
        conflicts=conflicting_evidence,
    )
    adaptive_escalation = decide_escalation(
        findings=finding_items,
        conflicts=conflicting_evidence,
        baseline_confidence=adaptive_confidence,
        confidence_threshold=0.55,
        force_deepen=False,
    )
    adaptive_stop = decide_stop(
        final_confidence=adaptive_confidence,
        confidence_threshold=0.55,
        findings_count=len(finding_items),
        conflicts_count=len(conflicting_evidence),
    )
    likely_issue_tracks = rank_likely_issue_tracks(
        findings=finding_items,
        conflicts=conflicting_evidence,
        changed=[],
    )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit",
        "workflow": "inspect-project",
        "project_dir": project_dir.as_posix(),
        "policy_path": policy_path.as_posix(),
        "ok": project_ok,
        "policy": policy,
        "summary": {
            "scopes": len(scopes),
            "inspect_fail_scopes": inspect_fail_scopes,
            "compare_fail_scopes": compare_fail_scopes,
            "total_findings": len(ordered_findings),
        },
        "inspect_runs": inspect_runs,
        "compare_runs": compare_runs,
        "findings": ordered_findings,
        "judgment": judgment,
        "adaptive": {
            "escalation": adaptive_escalation.as_dict(),
            "stop_decision": adaptive_stop.as_dict(),
            "likely_issue_tracks": likely_issue_tracks,
        },
        "evidence": {
            "machine_readable": "inspect-project.json",
            "human_readable": "inspect-project.txt",
            "manifest": "manifest.json",
        },
    }

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "project_dir": project_dir.as_posix(),
        "artifacts": {
            "inspect_project_json": "inspect-project.json",
            "inspect_project_txt": "inspect-project.txt",
        },
        "scopes": [
            {
                "scope": row["scope"],
                "inspect": row.get("inspect_artifacts", {}),
                "matched_files": row.get("matched_files", []),
            }
            for row in sorted(inspect_runs, key=lambda item: str(item["scope"]))
        ],
        "compare": sorted(compare_runs, key=lambda item: str(item["scope"])),
    }

    inspect_project_json = run_root / "inspect-project.json"
    inspect_project_txt = run_root / "inspect-project.txt"
    manifest_json = run_root / "manifest.json"
    inspect_project_json.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    inspect_project_txt.write_text(_render_text(payload), encoding="utf-8")
    manifest_json.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    if not ns.no_workspace:
        workspace_entry = record_workspace_run(
            workspace_root=workspace_root,
            workflow="inspect-project",
            scope=_safe_slug(project_dir.name),
            payload=payload,
            artifacts={
                "inspect_project_json": inspect_project_json.as_posix(),
                "inspect_project_txt": inspect_project_txt.as_posix(),
                "inspect_project_manifest": manifest_json.as_posix(),
            },
            recommendations=[f["message"] for f in ordered_findings[:10]],
        )
        payload["workspace"] = workspace_entry
        inspect_project_json.write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

    output = json.dumps(payload, sort_keys=True) if ns.format == "json" else _render_text(payload)
    sys.stdout.write(output + ("\n" if not output.endswith("\n") else ""))
    return EXIT_OK if payload["ok"] else EXIT_FINDINGS


MOCK_SCHEMA_VERSION = "sdetkit.mock_purity.v1"

_SAFE_ASCII_MAP: dict[str, str] = {chr(i): chr(i) for i in range(128)}
_SENSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "private",
    "secret",
    "token",
    "password",
    "passwd",
    "credential",
)

VALID_MOCK_ASSERTIONS: frozenset[str] = frozenset(
    {
        "assert_called",
        "assert_called_once",
        "assert_called_with",
        "assert_called_once_with",
        "assert_any_call",
        "assert_has_calls",
        "assert_not_called",
        "assert_awaited",
        "assert_awaited_once",
        "assert_awaited_with",
        "assert_awaited_once_with",
        "assert_any_await",
        "assert_has_awaits",
        "assert_not_awaited",
    }
)

STANDARD_UNITTEST_ASSERTIONS: frozenset[str] = frozenset(
    {
        "assertEqual",
        "assertNotEqual",
        "assertTrue",
        "assertFalse",
        "assertIs",
        "assertIsNot",
        "assertIsNone",
        "assertIsNotNone",
        "assertIn",
        "assertNotIn",
        "assertIsInstance",
        "assertNotIsInstance",
        "assertRaises",
        "assertRaisesRegex",
        "assertWarns",
        "assertWarnsRegex",
        "assertLogs",
        "assertNoLogs",
        "assertAlmostEqual",
        "assertNotAlmostEqual",
        "assertGreater",
        "assertGreaterEqual",
        "assertLess",
        "assertLessEqual",
        "assertRegex",
        "assertNotRegex",
        "assertCountEqual",
        "assertMultiLineEqual",
        "assertSequenceEqual",
        "assertListEqual",
        "assertTupleEqual",
        "assertSetEqual",
        "assertDictEqual",
        "assert_equal",
        "assert_not_equal",
        "assert_true",
        "assert_false",
        "assert_is",
        "assert_is_not",
        "assert_is_none",
        "assert_is_not_none",
        "assert_in",
        "assert_not_in",
        "assert_is_instance",
        "assert_not_is_instance",
        "assert_raises",
        "assert_almost_equal",
        "assert_greater",
        "assert_less",
    }
)

KNOWN_TYPO_ASSERTIONS: frozenset[str] = frozenset(
    {
        "assert_called_times",
        "assert_called_once_with_any",
        "assert_was_called",
        "assert_is_called",
        "assert_not_called_with",
        "assert_called_with_any",
        "assert_has_called",
        "assert_once_called",
        "assert_called_once_without_arguments",
        "assert_mock_called",
        "assert_called_with_args",
        "assert_times_called",
    }
)


def _safe_ident(raw: object) -> str:
    """Normalize, sanitize, and redact sensitive tokens from AST symbol names."""
    if not isinstance(raw, str):
        return "" if raw is None else str(raw)
    val = "".join(_SAFE_ASCII_MAP.get(ch, "") for ch in raw)
    for pat in _SENSITIVE_SUBSTRINGS:
        if pat in val.lower():
            val = re.sub(re.escape(pat), "safe", val, flags=re.IGNORECASE)
    return "".join(_SAFE_ASCII_MAP[ch] for ch in val if ch in _SAFE_ASCII_MAP)


def _sanitize_report_payload(obj: dict[str, Any]) -> dict[str, Any]:
    """Recursively map string leaves in report payload through constant ASCII table."""
    sanitized: dict[str, Any] = {}
    for k, v in obj.items():
        clean_k = "".join(_SAFE_ASCII_MAP.get(c, "") for c in str(k))
        if isinstance(v, str):
            sanitized[clean_k] = "".join(_SAFE_ASCII_MAP.get(c, "") for c in v)
        elif isinstance(v, list):
            sanitized[clean_k] = [
                (
                    "".join(_SAFE_ASCII_MAP.get(c, "") for c in item)
                    if isinstance(item, str)
                    else (_sanitize_report_payload(item) if isinstance(item, dict) else item)
                )
                for item in v
            ]
        elif isinstance(v, dict):
            sanitized[clean_k] = _sanitize_report_payload(v)
        else:
            sanitized[clean_k] = v
    return sanitized


class MockPurityVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self.findings: list[dict[str, Any]] = []
        self.mocks_detected: int = 0
        self.typo_assertion_count: int = 0
        self.unspecced_mock_count: int = 0
        self.leaked_patch_count: int = 0
        self.dormant_mock_count: int = 0

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._analyze_function(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def _analyze_function(self, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        fn_name = _safe_ident(fn.name)
        starts: list[tuple[int, int]] = []
        has_stop = False
        has_cleanup = False
        assigned_mocks: dict[str, tuple[int, int]] = {}

        for n in ast.walk(fn):
            if isinstance(n, ast.Call):
                func = n.func
                if isinstance(func, ast.Attribute) and func.attr == "start":
                    starts.append((n.lineno, n.col_offset))
                elif isinstance(func, ast.Attribute) and func.attr in ("stop", "stopall"):
                    has_stop = True
                elif isinstance(func, (ast.Name, ast.Attribute)):
                    attr_or_id = func.attr if isinstance(func, ast.Attribute) else func.id
                    if any(
                        term in attr_or_id.lower()
                        for term in ("cleanup", "finalizer", "monkeypatch")
                    ):
                        has_cleanup = True
            elif isinstance(n, ast.Assign):
                for target in n.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        val = n.value
                        if isinstance(val, ast.Call):
                            val_func = val.func
                            is_mock = False
                            if isinstance(val_func, ast.Name) and val_func.id in (
                                "Mock",
                                "MagicMock",
                                "AsyncMock",
                            ):
                                is_mock = True
                            elif isinstance(val_func, ast.Attribute) and val_func.attr in (
                                "Mock",
                                "MagicMock",
                                "AsyncMock",
                            ):
                                is_mock = True
                            if is_mock:
                                assigned_mocks[target.id] = (n.lineno, n.col_offset)

        if starts and not (has_stop or has_cleanup):
            for s_line, s_col in starts:
                self.leaked_patch_count += 1
                self.findings.append(
                    {
                        "file": self.rel_path,
                        "line": s_line,
                        "col": s_col,
                        "symbol": fn_name,
                        "smell_type": "LEAKED_PATCH",
                        "severity": "HIGH",
                        "description": f"patch.start() called without cleanup or stop() in '{fn_name}'",
                        "recommendation": (
                            "Register stop with addCleanup, use context manager 'with patch(...)', "
                            "or call patch.stop()."
                        ),
                    }
                )

        if assigned_mocks:
            load_counts = {var: 0 for var in assigned_mocks}
            for n in ast.walk(fn):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    if n.id in load_counts:
                        load_counts[n.id] += 1
            for var, count in load_counts.items():
                if count == 0:
                    v_line, v_col = assigned_mocks[var]
                    self.dormant_mock_count += 1
                    self.findings.append(
                        {
                            "file": self.rel_path,
                            "line": v_line,
                            "col": v_col,
                            "symbol": _safe_ident(var),
                            "smell_type": "DORMANT_MOCK",
                            "severity": "LOW",
                            "description": (
                                f"Mock variable '{var}' configured but never invoked or referenced in '{fn_name}'"
                            ),
                            "recommendation": "Pass the mock to target code under test or assert its interaction.",
                        }
                    )

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute):
            attr = func.attr
            if attr == "called":
                self.typo_assertion_count += 1
                self.findings.append(
                    {
                        "file": self.rel_path,
                        "line": node.lineno,
                        "col": node.col_offset,
                        "symbol": "called",
                        "smell_type": "TYPO_ASSERTION",
                        "severity": "HIGH",
                        "description": (
                            "Calling .called() as a function. 'called' is a boolean property; calling it returns a truthy Mock."
                        ),
                        "recommendation": "Use 'assert mock.called' or 'mock.assert_called()'.",
                    }
                )
            elif (
                attr.startswith("assert_")
                and attr not in VALID_MOCK_ASSERTIONS
                and attr not in STANDARD_UNITTEST_ASSERTIONS
            ):
                if (
                    attr in KNOWN_TYPO_ASSERTIONS
                    or "called" in attr
                    or "call" in attr
                    or "await" in attr
                    or "time" in attr
                ):
                    self.typo_assertion_count += 1
                    self.findings.append(
                        {
                            "file": self.rel_path,
                            "line": node.lineno,
                            "col": node.col_offset,
                            "symbol": _safe_ident(attr),
                            "smell_type": "TYPO_ASSERTION",
                            "severity": "HIGH",
                            "description": (
                                f"Misspelled mock assertion method '{attr}'. Mocks dynamically create attributes, so this call never asserts."
                            ),
                            "recommendation": "Replace with a valid mock assertion like 'assert_called_once_with(...)'.",
                        }
                    )

        is_mock_ctor = False
        ctor_name = ""
        if isinstance(func, ast.Name):
            if func.id in ("Mock", "MagicMock", "AsyncMock"):
                is_mock_ctor = True
                ctor_name = func.id
            elif func.id == "create_autospec":
                self.mocks_detected += 1
        elif isinstance(func, ast.Attribute):
            if func.attr in ("Mock", "MagicMock", "AsyncMock"):
                is_mock_ctor = True
                ctor_name = func.attr
            elif func.attr == "create_autospec":
                self.mocks_detected += 1

        if is_mock_ctor:
            self.mocks_detected += 1
            has_spec = any(
                kw.arg in ("spec", "spec_set", "autospec") for kw in node.keywords if kw.arg
            )
            if not has_spec:
                self.unspecced_mock_count += 1
                self.findings.append(
                    {
                        "file": self.rel_path,
                        "line": node.lineno,
                        "col": node.col_offset,
                        "symbol": _safe_ident(ctor_name),
                        "smell_type": "UNSPECCED_MOCK",
                        "severity": "MEDIUM",
                        "description": f"{ctor_name} created without spec, spec_set, or autospec.",
                        "recommendation": "Provide spec=TargetClass or use create_autospec to prevent silent attribute typos.",
                    }
                )

        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        if isinstance(node.value, ast.Attribute):
            attr = node.value.attr
            if attr in VALID_MOCK_ASSERTIONS:
                self.typo_assertion_count += 1
                self.findings.append(
                    {
                        "file": self.rel_path,
                        "line": node.lineno,
                        "col": node.col_offset,
                        "symbol": _safe_ident(attr),
                        "smell_type": "TYPO_ASSERTION",
                        "severity": "HIGH",
                        "description": (
                            f"Uncalled mock assertion '{attr}'. Attribute access without '()' does not execute assertion."
                        ),
                        "recommendation": f"Add parentheses to execute assertion: '{attr}()'.",
                    }
                )
        self.generic_visit(node)


def _discover_test_files(root: Path, targets: Sequence[str] | None = None) -> list[Path]:
    if targets:
        files: list[Path] = []
        for t in targets:
            tp = (root / t).resolve() if not Path(t).is_absolute() else Path(t).resolve()
            if tp.is_file() and tp.suffix == ".py":
                files.append(tp)
            elif tp.is_dir():
                for p in tp.rglob("*.py"):
                    if p.is_file():
                        files.append(p)
        return sorted(set(files))

    test_dirs = [root / "tests", root / "test"]
    discovered: set[Path] = set()
    for td in test_dirs:
        if td.is_dir():
            for p in td.rglob("*.py"):
                if p.is_file():
                    discovered.add(p)
    if not discovered:
        skip_dirs = {".git", ".venv", "venv", "build", "dist", "__pycache__", ".tox", ".eggs"}
        for p in root.rglob("*.py"):
            if any(part in skip_dirs for part in p.parts):
                continue
            name = p.name.lower()
            if (name.startswith("test_") or name.endswith("_test.py")) and p.is_file():
                discovered.add(p)
    return sorted(discovered)


def audit_mock_purity(
    root: Path,
    targets: Sequence[str] | None = None,
    min_score: float | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    test_files = _discover_test_files(root, targets)
    all_findings: list[dict[str, Any]] = []
    total_mocks = 0
    total_typo = 0
    total_unspecced = 0
    total_leaked = 0
    total_dormant = 0

    for tf in test_files:
        try:
            rel = tf.relative_to(root).as_posix()
        except ValueError:
            rel = tf.name
        try:
            source = tf.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=rel)
        except Exception:
            continue

        visitor = MockPurityVisitor(rel)
        visitor.visit(tree)

        all_findings.extend(visitor.findings)
        total_mocks += visitor.mocks_detected
        total_typo += visitor.typo_assertion_count
        total_unspecced += visitor.unspecced_mock_count
        total_leaked += visitor.leaked_patch_count
        total_dormant += visitor.dormant_mock_count

    penalty = (
        (total_typo * 25.0)
        + (total_leaked * 20.0)
        + (total_unspecced * 10.0)
        + (total_dormant * 5.0)
    )
    score = max(0.0, round(100.0 - penalty, 1))

    if min_score is not None:
        threshold = float(min_score)
    else:
        threshold = 100.0 if strict else 70.0

    if strict:
        ok = len(all_findings) == 0 and score >= threshold
    else:
        ok = score >= threshold and total_typo == 0 and total_leaked == 0

    verdict = "PASS" if ok else "FAIL"

    raw_report: dict[str, Any] = {
        "schema_version": MOCK_SCHEMA_VERSION,
        "repo_root": root.as_posix(),
        "verdict": verdict,
        "ok": ok,
        "mock_purity_score": score,
        "min_score": min_score,
        "strict": strict,
        "files_scanned": len(test_files),
        "mocks_detected": total_mocks,
        "findings_count": len(all_findings),
        "findings": all_findings,
        "smell_breakdown": {
            "typo_assertion": total_typo,
            "unspecced_mock": total_unspecced,
            "leaked_patch": total_leaked,
            "dormant_mock": total_dormant,
        },
    }
    return _sanitize_report_payload(raw_report)


def render_mock_purity_text(report: dict[str, Any]) -> str:
    verdict = str(report.get("verdict", "PASS"))
    score = float(report.get("mock_purity_score", 100.0))
    scanned = int(report.get("files_scanned", 0))
    mocks = int(report.get("mocks_detected", 0))
    total_findings = int(report.get("findings_count", 0))
    breakdown = report.get("smell_breakdown", {})
    if not isinstance(breakdown, dict):
        breakdown = {}

    typo_cnt = int(breakdown.get("typo_assertion", 0))
    leaked_cnt = int(breakdown.get("leaked_patch", 0))
    unspecced_cnt = int(breakdown.get("unspecced_mock", 0))
    dormant_cnt = int(breakdown.get("dormant_mock", 0))

    lines = [
        f"SDETKit Mock Purity Audit: verdict={verdict} score={score:.1f}/100",
        f"Files scanned: {scanned} | Mocks detected: {mocks} | Total findings: {total_findings}",
        (
            f"Smell Breakdown: typo_assertion={typo_cnt} "
            f"unspecced_mock={unspecced_cnt} "
            f"leaked_patch={leaked_cnt} "
            f"dormant_mock={dormant_cnt}"
        ),
    ]
    if total_findings > 0:
        lines.append(
            f"Detected {total_findings} mock purity smell(s). "
            "Run with --format json for full node coordinates."
        )
    else:
        lines.append("All audited mocks conform to purity standards.")
    return "\n".join(lines) + "\n"


def render_mock_purity_markdown(report: dict[str, Any]) -> str:
    verdict = str(report.get("verdict", "PASS"))
    score = float(report.get("mock_purity_score", 100.0))
    scanned = int(report.get("files_scanned", 0))
    mocks = int(report.get("mocks_detected", 0))
    total_findings = int(report.get("findings_count", 0))
    breakdown = report.get("smell_breakdown", {})
    if not isinstance(breakdown, dict):
        breakdown = {}

    typo_cnt = int(breakdown.get("typo_assertion", 0))
    leaked_cnt = int(breakdown.get("leaked_patch", 0))
    unspecced_cnt = int(breakdown.get("unspecced_mock", 0))
    dormant_cnt = int(breakdown.get("dormant_mock", 0))

    lines = [
        "# Mock Purity & Leakage Audit",
        "",
        f"- **Verdict**: `{verdict}`",
        f"- **Mock Purity Score**: `{score:.1f} / 100`",
        f"- **Files Scanned**: {scanned}",
        f"- **Mocks Detected**: {mocks}",
        f"- **Total Smells**: {total_findings}",
        "",
        "## Smell Category Breakdown",
        "",
        "| Smell Category | Severity | Detected Count | Description |",
        "| :--- | :--- | :--- | :--- |",
        f"| `TYPO_ASSERTION` | HIGH | {typo_cnt} | Typo assertion methods, uncalled assert attributes, or calling .called() |",
        f"| `LEAKED_PATCH` | HIGH | {leaked_cnt} | patch.start() without registered stop/cleanup |",
        f"| `UNSPECCED_MOCK` | MEDIUM | {unspecced_cnt} | Mock/MagicMock instantiated without spec/autospec |",
        f"| `DORMANT_MOCK` | LOW | {dormant_cnt} | Configured mock never invoked or asserted |",
        "",
    ]
    if total_findings > 0:
        lines.append(
            f"Detected {total_findings} mock purity finding(s). "
            "For granular AST coordinates and recommendations, inspect the JSON artifact or run with `--format json`."
        )
    else:
        lines.append("All audited mocks meet strict purity and isolation contracts.")
    return "\n".join(lines) + "\n"


def verify_mocks_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit verify-mocks",
        description="Audit test mock purity, uncalled assertions, unspecced mocks, and leaked patches",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root directory")
    parser.add_argument(
        "--targets",
        nargs="*",
        help="Optional test files or directories to audit (default: discover from tests/)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=None,
        help="Minimum allowable mock purity score (0-100)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: fail on any mock purity smell",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "md"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument("--out", help="Write report to file")
    parser.add_argument("--summary-out", help="Append markdown summary to file")

    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])
    root = Path(args.repo_root).resolve()

    try:
        report = audit_mock_purity(
            root=root,
            targets=args.targets,
            min_score=args.min_score,
            strict=args.strict,
        )
    except Exception as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2

    clean_report = _sanitize_report_payload(report)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(clean_report, indent=2) + "\n", encoding="utf-8")

    if args.summary_out:
        sm_path = Path(args.summary_out)
        sm_path.parent.mkdir(parents=True, exist_ok=True)
        with sm_path.open("a", encoding="utf-8") as sf:
            sf.write(render_mock_purity_markdown(clean_report))

    if args.format == "json":
        sys.stdout.write(json.dumps(clean_report, indent=2) + "\n")
    elif args.format in ("md", "markdown"):
        sys.stdout.write(render_mock_purity_markdown(clean_report))
    else:
        sys.stdout.write(render_mock_purity_text(clean_report))

    return 0 if clean_report.get("ok", True) else 2


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else list(sys.argv[1:])
    is_verify_mocks = (
        ("verify-mocks" in sys.argv)
        or ("verify_mocks" in sys.argv)
        or ("mocks" in sys.argv)
        or (os.environ.get("SDETKIT_SUBCOMMAND") in {"verify-mocks", "verify_mocks", "mocks"})
        or (bool(args_list) and args_list[0] in {"verify-mocks", "verify_mocks", "mocks"})
    )
    if is_verify_mocks:
        if args_list and args_list[0] in {"verify-mocks", "verify_mocks", "mocks"}:
            args_list = args_list[1:]
        return verify_mocks_main(args_list)
    return inspect_project_main(args_list)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
