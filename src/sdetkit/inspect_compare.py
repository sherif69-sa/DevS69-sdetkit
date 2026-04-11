from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .evidence_workspace import load_workspace_manifest, record_workspace_run

SCHEMA_VERSION = "sdetkit.inspect.compare.v1"
EXIT_OK = 0
EXIT_FINDINGS = 2


def _safe_slug(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "compare"


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"compare: expected JSON object at {path}")
    return loaded


def _read_workspace_record_payload(record_path: Path) -> dict[str, Any]:
    record = _load_json(record_path)
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"compare: workspace record missing payload object: {record_path}")
    return payload


def _resolve_workspace_record_path(*, workspace_root: Path, workflow: str, scope: str, run_hash: str) -> Path:
    manifest = load_workspace_manifest(workspace_root)
    runs = manifest.get("runs", [])
    if not isinstance(runs, list):
        raise ValueError("compare: workspace manifest runs must be an array")
    for item in runs:
        if not isinstance(item, dict):
            continue
        if (
            str(item.get("workflow", "")) == workflow
            and str(item.get("scope", "")) == scope
            and str(item.get("run_hash", "")) == run_hash
        ):
            record_path = workspace_root / str(item.get("record_path", ""))
            if not record_path.exists():
                raise ValueError(f"compare: workspace record path does not exist: {record_path}")
            return record_path
    raise ValueError(
        f"compare: workspace run not found for workflow={workflow!r}, scope={scope!r}, run_hash={run_hash!r}"
    )


def _resolve_latest_previous_record_paths(*, workspace_root: Path, workflow: str, scope: str) -> tuple[Path, Path]:
    manifest = load_workspace_manifest(workspace_root)
    runs = manifest.get("runs", [])
    if not isinstance(runs, list):
        raise ValueError("compare: workspace manifest runs must be an array")

    candidates: list[dict[str, Any]] = []
    for item in runs:
        if not isinstance(item, dict):
            continue
        if str(item.get("workflow", "")) != workflow or str(item.get("scope", "")) != scope:
            continue
        run_order = int(item.get("run_order", 0))
        record_path = workspace_root / str(item.get("record_path", ""))
        candidates.append(
            {
                "run_hash": str(item.get("run_hash", "")),
                "run_order": run_order,
                "record_path": record_path,
            }
        )

    by_hash: dict[str, dict[str, Any]] = {}
    for item in candidates:
        by_hash[item["run_hash"]] = item

    ordered = sorted(by_hash.values(), key=lambda row: (int(row["run_order"]), str(row["run_hash"])))
    if len(ordered) < 2:
        raise ValueError(
            "compare: latest-vs-previous requires at least two distinct recorded runs for "
            f"workflow={workflow!r}, scope={scope!r}"
        )
    previous = ordered[-2]
    latest = ordered[-1]
    for row in (previous, latest):
        if not row["record_path"].exists():
            raise ValueError(f"compare: workspace record path does not exist: {row['record_path']}")
    return Path(previous["record_path"]), Path(latest["record_path"])


def _diagnostics_delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, dict[str, int]]:
    keys = sorted(set(left) | set(right))
    return {
        key: {
            "baseline": int(left.get(key, 0)),
            "compare": int(right.get(key, 0)),
            "delta": int(right.get(key, 0)) - int(left.get(key, 0)),
        }
        for key in keys
    }


def _report_key(report: dict[str, Any]) -> str:
    return Path(str(report.get("path", "unknown"))).name


def _build_id_drift(left_reports: dict[str, dict[str, Any]], right_reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in sorted(set(left_reports) & set(right_reports)):
        left_ids = set(str(v) for v in left_reports[key].get("record_ids", []) if str(v))
        right_ids = set(str(v) for v in right_reports[key].get("record_ids", []) if str(v))
        disappeared = sorted(left_ids - right_ids)
        appeared = sorted(right_ids - left_ids)
        if disappeared or appeared:
            out.append(
                {
                    "file": key,
                    "disappeared_count": len(disappeared),
                    "appeared_count": len(appeared),
                    "disappeared_examples": disappeared[:20],
                    "appeared_examples": appeared[:20],
                }
            )
    return out


def _build_schema_drift(left_reports: dict[str, dict[str, Any]], right_reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    drift: list[dict[str, Any]] = []
    for key in sorted(set(left_reports) & set(right_reports)):
        left_cols = set(left_reports[key].get("schema_overview", {}).get("columns", []))
        right_cols = set(right_reports[key].get("schema_overview", {}).get("columns", []))
        removed = sorted(left_cols - right_cols)
        added = sorted(right_cols - left_cols)
        if removed or added:
            drift.append(
                {
                    "file": key,
                    "columns_removed": removed,
                    "columns_added": added,
                }
            )
    return drift


def _coverage_gap(report: dict[str, Any]) -> int:
    total = 0
    for item in report.get("rule_checks", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("rule_type", "")) == "expected_id_coverage":
            total += int(item.get("missing_expected_count", 0))
    return total


def _signal_counts(report: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    counts["suspicious_rows"] += int(report.get("diagnostics", {}).get("suspicious_row_count", 0))
    for item in report.get("suspicious_record_evidence", []):
        if not isinstance(item, dict):
            continue
        counts[str(item.get("signal", "unknown"))] += 1
    return counts


def _render_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"SDETKit inspect compare: {'NO_DRIFT' if payload['ok'] else 'DRIFT_DETECTED'}",
        f"baseline: {payload['baseline']['label']}",
        f"compare: {payload['compare']['label']}",
        f"files_added: {summary['files_added']}",
        f"files_removed: {summary['files_removed']}",
        f"id_drift_files: {summary['id_drift_files']}",
        f"schema_drift_files: {summary['schema_drift_files']}",
        "diagnostic_deltas:",
    ]
    for key, value in payload["diagnostic_deltas"].items():
        lines.append(f"- {key}: baseline={value['baseline']} compare={value['compare']} delta={value['delta']}")
    lines.append("recommendations:")
    for rec in payload["recommendations"]:
        lines.append(f"- {rec}")
    lines.append("")
    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit inspect-compare",
        description="Compare inspect evidence snapshots for baseline drift diagnostics.",
    )
    p.add_argument("--left", default=None, help="Path to baseline inspect.json or workspace record.json")
    p.add_argument("--right", default=None, help="Path to compare inspect.json or workspace record.json")
    p.add_argument("--left-run", default=None, help="Workspace run hash for baseline inspect run")
    p.add_argument("--right-run", default=None, help="Workspace run hash for compare inspect run")
    p.add_argument("--scope", default=None, help="Workspace scope (required for --left-run/--right-run)")
    p.add_argument("--latest-vs-previous", action="store_true", help="Compare latest workspace run against previous run for a scope")
    p.add_argument("--workspace-root", default=".sdetkit/workspace", help="Shared evidence workspace root")
    p.add_argument("--workflow", default="inspect", help="Workspace workflow to resolve runs from")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--out-dir", default=None, help="Directory for compare artifacts (default: .sdetkit/inspect-compare/<scope-or-input>)")
    p.add_argument("--no-workspace", action="store_true", help="Disable shared workspace run recording")
    return p


def _resolve_pair(ns: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    workspace_root = Path(ns.workspace_root)

    if ns.latest_vs_previous:
        if not ns.scope:
            raise ValueError("compare: --scope is required with --latest-vs-previous")
        left_record, right_record = _resolve_latest_previous_record_paths(
            workspace_root=workspace_root,
            workflow=str(ns.workflow),
            scope=str(ns.scope),
        )
        return (
            _read_workspace_record_payload(left_record),
            _read_workspace_record_payload(right_record),
            f"workspace:{left_record.as_posix()}",
            f"workspace:{right_record.as_posix()}",
        )

    if ns.left_run or ns.right_run:
        if not (ns.left_run and ns.right_run and ns.scope):
            raise ValueError("compare: --left-run and --right-run require --scope")
        left_record = _resolve_workspace_record_path(
            workspace_root=workspace_root,
            workflow=str(ns.workflow),
            scope=str(ns.scope),
            run_hash=str(ns.left_run),
        )
        right_record = _resolve_workspace_record_path(
            workspace_root=workspace_root,
            workflow=str(ns.workflow),
            scope=str(ns.scope),
            run_hash=str(ns.right_run),
        )
        return (
            _read_workspace_record_payload(left_record),
            _read_workspace_record_payload(right_record),
            f"workspace:{left_record.as_posix()}",
            f"workspace:{right_record.as_posix()}",
        )

    if ns.left and ns.right:
        left_path = Path(ns.left)
        right_path = Path(ns.right)

        left_loaded = _load_json(left_path)
        right_loaded = _load_json(right_path)

        left_payload = left_loaded.get("payload") if left_path.name == "record.json" else left_loaded
        right_payload = right_loaded.get("payload") if right_path.name == "record.json" else right_loaded
        if not isinstance(left_payload, dict) or not isinstance(right_payload, dict):
            raise ValueError("compare: expected inspect payload object for --left/--right")
        return left_payload, right_payload, left_path.as_posix(), right_path.as_posix()

    raise ValueError(
        "compare: provide either --left/--right, --left-run/--right-run with --scope, or --latest-vs-previous"
    )


def main(argv: list[str] | None = None) -> int:
    ns = _build_arg_parser().parse_args(argv)

    try:
        left_payload, right_payload, left_label, right_label = _resolve_pair(ns)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(str(exc) + "\n")
        return EXIT_FINDINGS

    left_reports = {
        _report_key(item): item
        for item in left_payload.get("file_reports", [])
        if isinstance(item, dict)
    }
    right_reports = {
        _report_key(item): item
        for item in right_payload.get("file_reports", [])
        if isinstance(item, dict)
    }

    files_added = sorted(set(right_reports) - set(left_reports))
    files_removed = sorted(set(left_reports) - set(right_reports))
    schema_drift = _build_schema_drift(left_reports, right_reports)
    id_drift = _build_id_drift(left_reports, right_reports)

    left_diag = left_payload.get("summary", {}).get("diagnostics", {})
    right_diag = right_payload.get("summary", {}).get("diagnostics", {})
    if not isinstance(left_diag, dict) or not isinstance(right_diag, dict):
        sys.stderr.write("compare: inspect payload missing summary.diagnostics object\n")
        return EXIT_FINDINGS
    diagnostic_deltas = _diagnostics_delta(left_diag, right_diag)

    left_coverage_gap = sum(_coverage_gap(r) for r in left_reports.values())
    right_coverage_gap = sum(_coverage_gap(r) for r in right_reports.values())

    left_signals: Counter[str] = Counter()
    right_signals: Counter[str] = Counter()
    for key in sorted(set(left_reports) & set(right_reports)):
        left_signals.update(_signal_counts(left_reports[key]))
        right_signals.update(_signal_counts(right_reports[key]))

    signal_drift = {
        key: {
            "baseline": int(left_signals.get(key, 0)),
            "compare": int(right_signals.get(key, 0)),
            "delta": int(right_signals.get(key, 0)) - int(left_signals.get(key, 0)),
        }
        for key in sorted(set(left_signals) | set(right_signals))
        if int(right_signals.get(key, 0)) != int(left_signals.get(key, 0))
    }

    duplicate_row_delta = int(right_diag.get("duplicate_row_groups", 0)) - int(
        left_diag.get("duplicate_row_groups", 0)
    )
    duplicate_record_id_delta = int(right_diag.get("duplicate_record_ids", 0)) - int(
        left_diag.get("duplicate_record_ids", 0)
    )

    drift_score = (
        len(files_added)
        + len(files_removed)
        + len(schema_drift)
        + len(id_drift)
        + abs(duplicate_row_delta)
        + abs(duplicate_record_id_delta)
        + abs(right_coverage_gap - left_coverage_gap)
        + len(signal_drift)
    )

    recommendations: list[str] = []
    if files_added or files_removed:
        recommendations.append("Review evidence file set drift before release signoff.")
    if schema_drift:
        recommendations.append("Schema drift detected; update ingest contracts or mapping rules.")
    if id_drift:
        recommendations.append("Record ID drift detected; validate disappear/appear sets for data loss risk.")
    if duplicate_row_delta > 0 or duplicate_record_id_delta > 0:
        recommendations.append("Duplicate signals increased; investigate export or dedupe regressions.")
    if right_coverage_gap > left_coverage_gap:
        recommendations.append("Expected ID coverage regressed; restore baseline coverage before promotion.")
    if not recommendations:
        recommendations.append("No meaningful drift detected; compare run is baseline-compatible.")

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit",
        "workflow": "inspect-compare",
        "ok": drift_score == 0,
        "baseline": {
            "label": left_label,
            "summary": left_payload.get("summary", {}),
        },
        "compare": {
            "label": right_label,
            "summary": right_payload.get("summary", {}),
        },
        "summary": {
            "files_added": len(files_added),
            "files_removed": len(files_removed),
            "schema_drift_files": len(schema_drift),
            "id_drift_files": len(id_drift),
            "coverage_gap_baseline": left_coverage_gap,
            "coverage_gap_compare": right_coverage_gap,
            "coverage_gap_delta": right_coverage_gap - left_coverage_gap,
            "duplicate_row_groups_delta": duplicate_row_delta,
            "duplicate_record_ids_delta": duplicate_record_id_delta,
            "signal_types_changed": len(signal_drift),
            "drift_score": drift_score,
        },
        "files_added": files_added,
        "files_removed": files_removed,
        "schema_drift": schema_drift,
        "id_drift": id_drift,
        "diagnostic_deltas": diagnostic_deltas,
        "signal_drift": signal_drift,
        "recommendations": recommendations,
        "evidence": {
            "machine_readable": "inspect-compare.json",
            "human_readable": "inspect-compare.txt",
        },
    }

    out_scope = ns.scope or _safe_slug(Path(left_label).name + "-vs-" + Path(right_label).name)
    out_dir = Path(ns.out_dir) if ns.out_dir else Path(".sdetkit") / "inspect-compare" / _safe_slug(out_scope)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "inspect-compare.json"
    txt_path = out_dir / "inspect-compare.txt"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    txt_path.write_text(_render_text(payload), encoding="utf-8")

    if not ns.no_workspace:
        workspace_entry = record_workspace_run(
            workspace_root=Path(ns.workspace_root),
            workflow="inspect-compare",
            scope=str(out_scope),
            payload=payload,
            artifacts={
                "inspect_compare_json": json_path.as_posix(),
                "inspect_compare_text": txt_path.as_posix(),
            },
            recommendations=list(payload.get("recommendations", [])),
        )
        payload["workspace"] = workspace_entry
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    output = json.dumps(payload, sort_keys=True) if ns.format == "json" else _render_text(payload)
    sys.stdout.write(output + ("\n" if not output.endswith("\n") else ""))
    return EXIT_OK if payload["ok"] else EXIT_FINDINGS


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
