from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .evidence_workspace import record_workspace_run
from .judgment import build_judgment, load_latest_previous_payload

SCHEMA_VERSION = "sdetkit.inspect.v2"
EXIT_OK = 0
EXIT_FINDINGS = 2
SUPPORTED_EXTENSIONS = {".csv", ".json"}
SUPPORTED_CROSS_FILE_MODES = {"left_subset", "exact_match"}
RULES_TEMPLATE: dict[str, Any] = {
    "files": {
        "orders.csv": {
            "required_columns": ["id", "status", "amount"],
            "key_columns": ["id"],
            "schema_expectations": {"amount": ["numeric_string"], "status": ["string"]},
            "id_column": "id",
            "expected_ids": ["A100", "A101"],
        },
        "snapshot.json": {
            "id_column": "entity_id",
        },
    },
    "cross_file_rules": [
        {
            "name": "orders_covered_by_snapshot",
            "left_file": "orders.csv",
            "left_id_column": "id",
            "right_file": "snapshot.json",
            "right_id_column": "entity_id",
            "mode": "left_subset",
        }
    ],
}


def _safe_slug(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "input"


def _read_json_records(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    notes: list[str] = []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
        dropped = len(payload) - len(rows)
        if dropped:
            notes.append(f"dropped {dropped} non-object records from top-level array")
        return rows, notes
    if isinstance(payload, dict):
        if isinstance(payload.get("records"), list):
            records = payload["records"]
            rows = [row for row in records if isinstance(row, dict)]
            dropped = len(records) - len(rows)
            if dropped:
                notes.append(f"dropped {dropped} non-object records under records key")
            return rows, notes
        return [payload], notes
    raise ValueError("JSON input must be an object, an array of objects, or include records[].")


def _read_csv_records(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    notes: list[str] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        if reader.fieldnames is None:
            notes.append("csv has no header row")
    return rows, notes


def _row_fingerprint(row: dict[str, Any]) -> str:
    stable = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _infer_type_tag(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return "empty"
        if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
            return "numeric_string"
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _find_record_id_field(rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    preferred = ("id", "record_id", "user_id", "order_id", "account_id")
    keys = set().union(*(row.keys() for row in rows if isinstance(row, dict)))
    for field in preferred:
        if field in keys:
            return field
    return None


def _relative_key(path: Path, *, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _matches_file_rule(path: Path, *, root: Path, rule_key: str) -> bool:
    return rule_key in {path.name, path.as_posix(), _relative_key(path, root=root)}


def _normalize_value_set(values: list[Any]) -> set[str]:
    return {str(v) for v in values if not _missing(v)}


def _apply_file_rules(
    *,
    path: Path,
    root: Path,
    rows: list[dict[str, Any]],
    columns: list[str],
    rules: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, set[str]]]:
    if not rules:
        return [], [], {}

    rule_results: list[dict[str, Any]] = []
    suspicious_evidence: list[dict[str, Any]] = []
    extracted_sets: dict[str, set[str]] = {}

    required_columns = sorted(str(v) for v in rules.get("required_columns", []) if str(v))
    if required_columns:
        missing_required = sorted(col for col in required_columns if col not in columns)
        rule_results.append(
            {
                "rule_type": "required_columns",
                "ok": len(missing_required) == 0,
                "missing_columns": missing_required,
            }
        )

    key_columns = [str(v) for v in rules.get("key_columns", []) if str(v)]
    if key_columns:
        duplicate_counts: Counter[str] = Counter()
        key_samples: dict[str, dict[str, Any]] = {}
        key_first_index: dict[str, int] = {}
        for idx, row in enumerate(rows):
            key_payload = {k: row.get(k) for k in key_columns}
            if any(_missing(v) for v in key_payload.values()):
                continue
            key_hash = _row_fingerprint(key_payload)
            duplicate_counts[key_hash] += 1
            key_samples.setdefault(key_hash, key_payload)
            key_first_index.setdefault(key_hash, idx)
        duplicate_key_groups = [
            {
                "first_row_index": key_first_index[h],
                "duplicate_count": count,
                "key_values": key_samples[h],
            }
            for h, count in sorted(duplicate_counts.items())
            if count > 1
        ]
        rule_results.append(
            {
                "rule_type": "duplicate_keys",
                "ok": len(duplicate_key_groups) == 0,
                "key_columns": key_columns,
                "duplicate_groups": duplicate_key_groups[:20],
            }
        )
        for group in duplicate_key_groups[:20]:
            suspicious_evidence.append(
                {
                    "signal": "duplicate_key",
                    "row_index": group["first_row_index"],
                    "details": group["key_values"],
                }
            )

    schema_expectations = rules.get("schema_expectations", {})
    if isinstance(schema_expectations, dict) and schema_expectations:
        expectation_violations: list[dict[str, Any]] = []
        for col in sorted(schema_expectations):
            allowed = sorted(str(v) for v in schema_expectations[col] if str(v))
            if col not in columns:
                expectation_violations.append(
                    {
                        "column": col,
                        "error": "column_missing",
                        "allowed_types": allowed,
                    }
                )
                continue
            unexpected: Counter[str] = Counter()
            for row in rows:
                tag = _infer_type_tag(row.get(col))
                if tag not in set(allowed):
                    unexpected[tag] += 1
            if unexpected:
                expectation_violations.append(
                    {
                        "column": col,
                        "unexpected_type_counts": dict(sorted(unexpected.items())),
                        "allowed_types": allowed,
                    }
                )
        rule_results.append(
            {
                "rule_type": "schema_expectations",
                "ok": len(expectation_violations) == 0,
                "violations": expectation_violations,
            }
        )

    id_column = rules.get("id_column")
    if isinstance(id_column, str) and id_column:
        observed_ids = _normalize_value_set([row.get(id_column) for row in rows])
        extracted_sets[id_column] = observed_ids
        expected_ids = rules.get("expected_ids", [])
        if isinstance(expected_ids, list):
            expected_set = _normalize_value_set(expected_ids)
            missing_expected = sorted(expected_set - observed_ids)
            unexpected_observed = sorted(observed_ids - expected_set)
            rule_results.append(
                {
                    "rule_type": "expected_id_coverage",
                    "ok": len(missing_expected) == 0,
                    "id_column": id_column,
                    "missing_expected_count": len(missing_expected),
                    "missing_expected_examples": missing_expected[:20],
                    "unexpected_observed_count": len(unexpected_observed),
                    "unexpected_observed_examples": unexpected_observed[:20],
                }
            )

    return rule_results, suspicious_evidence, extracted_sets


def _analyze_file(path: Path, *, root: Path, file_rules: dict[str, Any]) -> dict[str, Any]:
    ext = path.suffix.lower()
    if ext == ".csv":
        rows, notes = _read_csv_records(path)
        source_kind = "csv"
    elif ext == ".json":
        rows, notes = _read_json_records(path)
        source_kind = "json"
    else:
        raise ValueError(f"unsupported file extension: {path.suffix}")

    columns = sorted(set().union(*(row.keys() for row in rows))) if rows else []

    missing_counts: dict[str, int] = {col: 0 for col in columns}
    type_tags: dict[str, Counter[str]] = {col: Counter() for col in columns}
    suspicious_rows: list[dict[str, Any]] = []

    row_hashes: Counter[str] = Counter()
    row_hash_to_index: dict[str, int] = {}

    for idx, row in enumerate(rows):
        row_hash = _row_fingerprint(row)
        row_hashes[row_hash] += 1
        row_hash_to_index.setdefault(row_hash, idx)

        row_issues: list[str] = []
        for col in columns:
            value = row.get(col)
            if _missing(value):
                missing_counts[col] += 1
            type_tags[col][_infer_type_tag(value)] += 1

            if isinstance(value, str):
                if value != value.strip():
                    row_issues.append(f"{col}: leading_or_trailing_whitespace")
                if any(ord(ch) < 32 and ch not in {"\t", "\n", "\r"} for ch in value):
                    row_issues.append(f"{col}: control_characters")

        if row_issues:
            suspicious_rows.append(
                {
                    "row_index": idx,
                    "issues": sorted(set(row_issues)),
                    "record_preview": {k: row.get(k) for k in columns[:4]},
                }
            )

    duplicate_rows = [
        {
            "row_index": row_hash_to_index[h],
            "duplicate_count": c,
            "fingerprint": h,
        }
        for h, c in sorted(row_hashes.items())
        if c > 1
    ]

    missing_columns = [
        {"column": col, "missing_count": cnt}
        for col, cnt in sorted(missing_counts.items())
        if cnt > 0
    ]

    inconsistent_type_columns = []
    for col, tags in sorted(type_tags.items()):
        live = {tag: count for tag, count in tags.items() if count > 0 and tag != "empty"}
        if len(live) > 1:
            inconsistent_type_columns.append({"column": col, "type_counts": live})

    record_id_field = _find_record_id_field(rows)
    record_ids: set[str] = set()
    duplicate_record_ids: dict[str, int] = {}
    if record_id_field:
        id_counter: Counter[str] = Counter()
        for row in rows:
            value = row.get(record_id_field)
            if _missing(value):
                continue
            normalized = str(value)
            id_counter[normalized] += 1
        record_ids = {record_id for record_id, count in id_counter.items() if count >= 1}
        duplicate_record_ids = {
            record_id: count for record_id, count in sorted(id_counter.items()) if count > 1
        }

    rules_for_file: dict[str, Any] | None = None
    for rule_key, rule_value in sorted(file_rules.items()):
        if _matches_file_rule(path, root=root, rule_key=str(rule_key)):
            rules_for_file = rule_value if isinstance(rule_value, dict) else None
            break
    rule_results, suspicious_rule_evidence, extracted_sets = _apply_file_rules(
        path=path,
        root=root,
        rows=rows,
        columns=columns,
        rules=rules_for_file,
    )
    failed_rule_count = sum(1 for item in rule_results if not bool(item.get("ok", False)))

    diagnostics = {
        "suspicious_row_count": len(suspicious_rows),
        "missing_value_columns": len(missing_columns),
        "duplicate_row_groups": len(duplicate_rows),
        "inconsistent_type_columns": len(inconsistent_type_columns),
        "duplicate_record_id_count": len(duplicate_record_ids),
        "failed_rule_checks": failed_rule_count,
    }

    findings = sum(int(value) for value in diagnostics.values())
    confidence = max(0.0, round(1.0 - min(findings, 20) / 20.0, 2))

    return {
        "path": path.as_posix(),
        "source_kind": source_kind,
        "row_count": len(rows),
        "schema_overview": {"columns": columns},
        "diagnostics": diagnostics,
        "suspicious_rows": suspicious_rows[:50],
        "missing_values": missing_columns,
        "duplicate_rows": duplicate_rows,
        "inconsistent_values": inconsistent_type_columns,
        "record_id_field": record_id_field,
        "record_id_duplicates": duplicate_record_ids,
        "record_ids": sorted(record_ids),
        "rule_checks": rule_results,
        "suspicious_record_evidence": sorted(
            suspicious_rule_evidence,
            key=lambda item: (
                str(item.get("signal", "")),
                int(item.get("row_index", -1)),
                json.dumps(item.get("details", {}), sort_keys=True),
            ),
        )[:50],
        "extracted_id_sets": {name: sorted(values) for name, values in sorted(extracted_sets.items())},
        "confidence": confidence,
        "recommendations": _recommendations(diagnostics, record_id_field is not None),
        "notes": notes,
    }


def _recommendations(diagnostics: dict[str, int], has_record_ids: bool) -> list[str]:
    recs: list[str] = []
    if diagnostics["missing_value_columns"]:
        recs.append("Backfill or validate required fields before release decisioning.")
    if diagnostics["duplicate_row_groups"]:
        recs.append("De-duplicate repeated records in source export or ETL stage.")
    if diagnostics["inconsistent_type_columns"]:
        recs.append("Standardize inconsistent column types to a single operational shape.")
    if has_record_ids and diagnostics["duplicate_record_id_count"]:
        recs.append("Resolve duplicate record IDs to keep cross-file joins deterministic.")
    if not recs:
        recs.append("No high-signal anomalies detected; keep this snapshot as baseline evidence.")
    return recs


def _discover_supported_files(target: Path) -> tuple[list[Path], list[Path]]:
    if target.is_file():
        if target.suffix.lower() in SUPPORTED_EXTENSIONS:
            return [target], []
        return [], [target]

    supported: list[Path] = []
    skipped: list[Path] = []
    for candidate in sorted(target.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
            supported.append(candidate)
        else:
            skipped.append(candidate)
    return supported, skipped


def _cross_file_diagnostics(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with_ids = [r for r in reports if r.get("record_id_field") and r.get("record_ids")]
    mismatches: list[dict[str, Any]] = []
    for idx, base in enumerate(with_ids):
        base_ids = set(base.get("record_ids", []))
        for other in with_ids[idx + 1 :]:
            other_ids = set(other.get("record_ids", []))
            only_base = sorted(base_ids - other_ids)
            only_other = sorted(other_ids - base_ids)
            if only_base or only_other:
                mismatches.append(
                    {
                        "left_path": base["path"],
                        "right_path": other["path"],
                        "left_only_count": len(only_base),
                        "right_only_count": len(only_other),
                        "left_only_examples": only_base[:10],
                        "right_only_examples": only_other[:10],
                    }
                )
    return mismatches


def _rule_cross_file_checks(
    reports: list[dict[str, Any]], rules: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for report in reports:
        by_path[report["path"]] = report
        by_name[Path(report["path"]).name] = report

    results: list[dict[str, Any]] = []
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        left_file = str(rule.get("left_file", ""))
        right_file = str(rule.get("right_file", ""))
        left_column = str(rule.get("left_id_column", ""))
        right_column = str(rule.get("right_id_column", ""))
        mode = str(rule.get("mode", "left_subset"))
        name = str(rule.get("name", f"cross_rule_{idx + 1}"))
        left = by_path.get(left_file) or by_name.get(left_file)
        right = by_path.get(right_file) or by_name.get(right_file)
        if not left or not right:
            results.append(
                {
                    "rule_type": "cross_file_match",
                    "name": name,
                    "ok": False,
                    "error": "file_not_found",
                    "left_file": left_file,
                    "right_file": right_file,
                }
            )
            continue
        left_ids = set(left.get("extracted_id_sets", {}).get(left_column, []))
        right_ids = set(right.get("extracted_id_sets", {}).get(right_column, []))
        left_only = sorted(left_ids - right_ids)
        right_only = sorted(right_ids - left_ids)
        ok = len(left_only) == 0 if mode == "left_subset" else len(left_only) == 0 and len(right_only) == 0
        results.append(
            {
                "rule_type": "cross_file_match",
                "name": name,
                "mode": mode,
                "ok": ok,
                "left_file": left["path"],
                "right_file": right["path"],
                "left_only_count": len(left_only),
                "right_only_count": len(right_only),
                "left_only_examples": left_only[:20],
                "right_only_examples": right_only[:20],
            }
        )
    return results


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"SDETKit inspect: {'OK' if payload['ok'] else 'FINDINGS'}",
        f"input: {payload['input_path']}",
        f"files_analyzed: {payload['summary']['files_analyzed']}",
        f"total_records: {payload['summary']['total_records']}",
        f"confidence: {payload['confidence']}",
        "diagnostics:",
    ]
    for key, value in payload["summary"]["diagnostics"].items():
        lines.append(f"- {key}: {value}")
    if payload.get("cross_file_mismatches"):
        lines.append("cross_file_mismatches:")
        for item in payload["cross_file_mismatches"]:
            lines.append(
                f"- {item['left_path']} vs {item['right_path']}: "
                f"left_only={item['left_only_count']} right_only={item['right_only_count']}"
            )
    judgment = payload.get("judgment", {})
    if isinstance(judgment, dict):
        lines.append("judgment_summary:")
        lines.append(
            f"- status={judgment.get('status')} severity={judgment.get('severity')} confidence={judgment.get('confidence', {}).get('score')}"
        )
        top = judgment.get("top_judgment", {})
        if isinstance(top, dict):
            lines.append(f"- next_move: {top.get('next_move', '')}")
        contradictions = judgment.get("contradictions", [])
        if isinstance(contradictions, list) and contradictions:
            lines.append(f"- contradictions: {len(contradictions)}")
    lines.append("recommendations:")
    for rec in payload["recommendations"]:
        lines.append(f"- {rec}")
    lines.append("")
    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit inspect",
        description="Inspect CSV/JSON business evidence and emit deterministic diagnostics.",
    )
    p.add_argument("path", nargs="?", help="CSV/JSON file or folder containing evidence files")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument(
        "--out-dir",
        default=None,
        help="Directory for artifact outputs (default: .sdetkit/inspect/<input-name>).",
    )
    p.add_argument(
        "--rules",
        default=None,
        help="Optional JSON rules file. Use --rules-template for the canonical shape.",
    )
    p.add_argument(
        "--rules-template",
        action="store_true",
        help="Print a canonical inspect rules JSON template and exit.",
    )
    p.add_argument(
        "--rules-lint",
        default=None,
        help="Validate an inspect rules JSON file and exit (no dataset scan).",
    )
    p.add_argument(
        "--workspace-root",
        default=".sdetkit/workspace",
        help="Shared evidence workspace root for inspect/doctor run records.",
    )
    p.add_argument(
        "--no-workspace",
        action="store_true",
        help="Disable shared workspace run recording.",
    )
    return p


def _validate_rules_payload(rules_payload: dict[str, Any]) -> str | None:
    unknown_top_level = sorted(k for k in rules_payload if k not in {"files", "cross_file_rules"})
    if unknown_top_level:
        return (
            "inspect: invalid rules payload: unknown top-level key(s): "
            + ", ".join(repr(key) for key in unknown_top_level)
            + "; expected only 'files' and 'cross_file_rules'"
        )

    file_rules = rules_payload.get("files", {})
    if not isinstance(file_rules, dict):
        return "inspect: invalid rules payload: 'files' must be an object keyed by file name or path"
    for file_key, item in sorted(file_rules.items()):
        key = str(file_key)
        if not key:
            return "inspect: invalid file rule key: empty file key is not allowed"
        if not isinstance(item, dict):
            return f"inspect: invalid files[{key!r}]: each file rule must be an object"
        required_columns = item.get("required_columns")
        if required_columns is not None and not isinstance(required_columns, list):
            return f"inspect: invalid files[{key!r}].required_columns: must be an array of strings"
        key_columns = item.get("key_columns")
        if key_columns is not None and not isinstance(key_columns, list):
            return f"inspect: invalid files[{key!r}].key_columns: must be an array of strings"
        schema_expectations = item.get("schema_expectations")
        if schema_expectations is not None and not isinstance(schema_expectations, dict):
            return f"inspect: invalid files[{key!r}].schema_expectations: must be an object"
        if isinstance(schema_expectations, dict):
            for col_name, allowed_types in sorted(schema_expectations.items()):
                if not isinstance(allowed_types, list):
                    return (
                        "inspect: invalid files["
                        f"{key!r}].schema_expectations[{str(col_name)!r}]: must be an array of type tags"
                    )
        id_column = item.get("id_column")
        if id_column is not None and (not isinstance(id_column, str) or not id_column.strip()):
            return f"inspect: invalid files[{key!r}].id_column: must be a non-empty string"
        expected_ids = item.get("expected_ids")
        if expected_ids is not None and not isinstance(expected_ids, list):
            return f"inspect: invalid files[{key!r}].expected_ids: must be an array"

    cross_file_rules = rules_payload.get("cross_file_rules", [])
    if not isinstance(cross_file_rules, list):
        return "inspect: invalid rules payload: 'cross_file_rules' must be an array"

    for idx, item in enumerate(cross_file_rules):
        if not isinstance(item, dict):
            return f"inspect: invalid cross_file_rules[{idx}]: each rule must be an object"
        mode = item.get("mode", "left_subset")
        if str(mode) not in SUPPORTED_CROSS_FILE_MODES:
            supported = ", ".join(sorted(SUPPORTED_CROSS_FILE_MODES))
            return (
                f"inspect: invalid cross_file_rules[{idx}].mode: {mode!r}; "
                f"supported values: {supported}"
            )
        for field in ("left_file", "right_file", "left_id_column", "right_id_column"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                return (
                    "inspect: invalid cross_file_rules["
                    f"{idx}].{field}: must be a non-empty string"
                )
    return None


def _load_rules_payload(path: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"inspect: rules file does not exist: {path}"
    except json.JSONDecodeError as exc:
        return None, (
            "inspect: invalid rules file JSON at "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        )
    if not isinstance(loaded, dict):
        return None, "inspect: invalid rules payload: top-level JSON value must be an object"
    validation_error = _validate_rules_payload(loaded)
    if validation_error:
        return None, validation_error
    return loaded, None


def run_inspect(
    *,
    input_path: Path,
    out_dir: Path,
    rules_payload: dict[str, Any] | None = None,
    workspace_root: Path = Path(".sdetkit/workspace"),
    record_workspace: bool = True,
    workspace_scope: str | None = None,
) -> tuple[int, dict[str, Any], Path, Path]:
    target = input_path.resolve()
    if not target.exists():
        raise ValueError(f"inspect: input path does not exist: {target}")

    files, skipped = _discover_supported_files(target)
    if not files:
        raise ValueError("inspect: no supported evidence files found (expected .csv or .json)")

    loaded_rules = rules_payload if isinstance(rules_payload, dict) else {}
    validation_error = _validate_rules_payload(loaded_rules)
    if validation_error:
        raise ValueError(validation_error)

    file_rules = loaded_rules.get("files", {})
    cross_file_rules = loaded_rules.get("cross_file_rules", [])
    reports = [
        _analyze_file(path, root=target if target.is_dir() else target.parent, file_rules=file_rules)
        for path in files
    ]
    cross_file = _cross_file_diagnostics(reports)
    cross_file_rule_results = _rule_cross_file_checks(reports, cross_file_rules)

    summary = {
        "files_analyzed": len(reports),
        "total_records": sum(int(r["row_count"]) for r in reports),
        "skipped_file_count": len(skipped),
        "diagnostics": {
            "suspicious_rows": sum(int(r["diagnostics"]["suspicious_row_count"]) for r in reports),
            "missing_value_columns": sum(
                int(r["diagnostics"]["missing_value_columns"]) for r in reports
            ),
            "duplicate_row_groups": sum(
                int(r["diagnostics"]["duplicate_row_groups"]) for r in reports
            ),
            "inconsistent_type_columns": sum(
                int(r["diagnostics"]["inconsistent_type_columns"]) for r in reports
            ),
            "duplicate_record_ids": sum(
                int(r["diagnostics"]["duplicate_record_id_count"]) for r in reports
            ),
            "cross_file_mismatches": len(cross_file),
            "failed_rule_checks": sum(int(r["diagnostics"]["failed_rule_checks"]) for r in reports)
            + sum(1 for item in cross_file_rule_results if not bool(item.get("ok", False))),
        },
    }

    findings_score = sum(int(v) for v in summary["diagnostics"].values())
    confidence = max(0.0, round(1.0 - min(findings_score, 30) / 30.0, 2))
    recommendations: list[str] = []
    for report in reports:
        for rec in report["recommendations"]:
            if rec not in recommendations:
                recommendations.append(rec)
    if cross_file:
        recommendations.append("Align record IDs across related exports before trusting combined metrics.")

    previous_payload = None
    previous_hash = None
    scope_name = workspace_scope if workspace_scope else _safe_slug(target.name)
    if record_workspace:
        previous_payload, previous_hash = load_latest_previous_payload(
            workspace_root=workspace_root,
            workflow="inspect",
            scope=scope_name,
        )

    finding_items: list[dict[str, Any]] = []
    for key, value in summary["diagnostics"].items():
        if int(value) <= 0:
            continue
        finding_items.append(
            {
                "id": f"inspect:{key}",
                "kind": key,
                "severity": "high" if key in {"cross_file_mismatches", "failed_rule_checks"} else "medium",
                "priority": min(50, int(value) * 8),
                "why_it_matters": f"{key} surfaced {value} time(s) in this run.",
                "next_action": recommendations[0] if recommendations else "Review evidence anomalies.",
                "message": f"{key}={value}",
            }
        )
    conflicting_evidence: list[dict[str, Any]] = []
    if cross_file and summary["diagnostics"].get("missing_value_columns", 0) == 0:
        conflicting_evidence.append(
            {
                "id": "inspect:cross-file-vs-local",
                "kind": "cross_surface_disagreement",
                "message": "Cross-file mismatches exist despite clean local missing-value signal.",
            }
        )

    supporting_evidence = [
        {"kind": key, "value": int(value)}
        for key, value in sorted(summary["diagnostics"].items())
        if int(value) > 0
    ]
    stability = 0.7
    previous_summary = None
    if isinstance(previous_payload, dict):
        prev_diag = previous_payload.get("summary", {}).get("diagnostics", {})
        if isinstance(prev_diag, dict):
            prev_total = sum(int(prev_diag.get(k, 0)) for k in summary["diagnostics"])
            cur_total = sum(int(v) for v in summary["diagnostics"].values())
            if cur_total > prev_total:
                stability = 0.35
                previous_summary = "regressing"
            elif cur_total < prev_total:
                stability = 0.85
                previous_summary = "improving"
            else:
                stability = 0.7

    inspect_ok = findings_score == 0
    blocking = (
        int(summary["diagnostics"].get("cross_file_mismatches", 0)) > 0
        or int(summary["diagnostics"].get("failed_rule_checks", 0)) > 0
    )
    judgment = build_judgment(
        workflow="inspect",
        findings=finding_items,
        supporting_evidence=supporting_evidence,
        conflicting_evidence=conflicting_evidence,
        completeness=1.0 if summary["files_analyzed"] > 0 else 0.3,
        stability=stability,
        previous_summary=previous_summary,
        workflow_ok=inspect_ok,
        blocking=blocking,
    )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit",
        "workflow": "inspect",
        "input_path": target.as_posix(),
        "ok": inspect_ok,
        "summary": summary,
        "file_reports": reports,
        "cross_file_mismatches": cross_file,
        "cross_file_rule_checks": cross_file_rule_results,
        "recommendations": recommendations,
        "confidence": confidence,
        "judgment": judgment,
        "evidence": {
            "machine_readable": "inspect.json",
            "human_readable": "inspect.txt",
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "inspect.json"
    txt_path = out_dir / "inspect.txt"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    txt_path.write_text(_render_text(payload), encoding="utf-8")

    if record_workspace:
        workspace_entry = record_workspace_run(
            workspace_root=workspace_root,
            workflow="inspect",
            scope=scope_name,
            payload=payload,
            artifacts={
                "inspect_json": json_path.as_posix(),
                "inspect_text": txt_path.as_posix(),
            },
            recommendations=list(payload.get("recommendations", [])),
        )
        payload["workspace"] = workspace_entry
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return (EXIT_OK if payload["ok"] else EXIT_FINDINGS), payload, json_path, txt_path


def main(argv: list[str] | None = None) -> int:
    ns = _build_arg_parser().parse_args(argv)
    if ns.rules and ns.rules_template:
        sys.stderr.write("inspect: --rules and --rules-template cannot be used together\n")
        return EXIT_FINDINGS
    if ns.rules_lint and ns.rules_template:
        sys.stderr.write("inspect: --rules-lint and --rules-template cannot be used together\n")
        return EXIT_FINDINGS
    if ns.rules_lint and ns.rules:
        sys.stderr.write("inspect: --rules-lint and --rules cannot be used together\n")
        return EXIT_FINDINGS

    if ns.rules_template:
        sys.stdout.write(json.dumps(RULES_TEMPLATE, indent=2, sort_keys=True) + "\n")
        return EXIT_OK

    if ns.rules_lint:
        _, error = _load_rules_payload(ns.rules_lint)
        if error:
            sys.stderr.write(f"inspect: rules lint FAILED: {error}\n")
            return EXIT_FINDINGS
        sys.stdout.write("inspect: rules lint OK\n")
        return EXIT_OK

    if not ns.path:
        sys.stderr.write("inspect: missing input path (or use --rules-template)\n")
        return EXIT_FINDINGS

    target = Path(ns.path).resolve()

    rules_payload: dict[str, Any] = {}
    if ns.rules:
        loaded, error = _load_rules_payload(ns.rules)
        if error:
            sys.stderr.write(error + "\n")
            return EXIT_FINDINGS
        rules_payload = loaded if loaded is not None else {}
    out_dir = Path(ns.out_dir) if ns.out_dir else Path(".sdetkit") / "inspect" / _safe_slug(target.name)
    try:
        rc, payload, _, _ = run_inspect(
            input_path=target,
            out_dir=out_dir,
            rules_payload=rules_payload,
            workspace_root=Path(ns.workspace_root),
            record_workspace=not ns.no_workspace,
        )
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return EXIT_FINDINGS

    output = json.dumps(payload, sort_keys=True) if ns.format == "json" else _render_text(payload)
    sys.stdout.write(output + ("\n" if not output.endswith("\n") else ""))
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
