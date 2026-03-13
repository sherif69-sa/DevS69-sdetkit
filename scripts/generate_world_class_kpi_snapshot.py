from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


def _default_snapshot_date() -> str:
    return date.today().isoformat()


def _validate_snapshot_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"invalid --snapshot-date {value!r}; expected YYYY-MM-DD") from exc
    return parsed.isoformat()


def _normalize_metric_value(value: str) -> tuple[float, str] | None:
    raw = value.strip().lower()
    if raw.endswith("%"):
        number = raw.removesuffix("%").strip()
        try:
            return float(number), "%"
        except ValueError:
            return None
    if raw.endswith("h"):
        number = raw.removesuffix("h").strip()
        try:
            return float(number), "h"
        except ValueError:
            return None
    if raw.endswith("m"):
        number = raw.removesuffix("m").strip()
        try:
            return float(number), "m"
        except ValueError:
            return None
    try:
        return float(raw), ""
    except ValueError:
        return None


def _format_delta(current_value: str, previous_value: str) -> str:
    current = _normalize_metric_value(current_value)
    previous = _normalize_metric_value(previous_value)
    if current is None or previous is None:
        return "n/a"
    current_num, current_unit = current
    previous_num, previous_unit = previous
    if current_unit != previous_unit:
        return "n/a"
    delta = current_num - previous_num
    sign = "+" if delta > 0 else ""
    if current_unit:
        return f"{sign}{delta:.2f}{current_unit}"
    return f"{sign}{delta:.2f}"


def _parse_target_expression(target: str) -> tuple[str, float, str] | None:
    normalized = target.replace(" ", "")
    for op in (">=", "<=", ">", "<"):
        if normalized.startswith(op):
            parsed = _normalize_metric_value(normalized[len(op) :])
            if parsed is None:
                return None
            value, unit = parsed
            return op, value, unit
    return None


def _evaluate_target_status(current_value: str, target: str) -> str:
    current = _normalize_metric_value(current_value)
    target_expr = _parse_target_expression(target)
    if current is None or target_expr is None:
        return "unknown"

    current_num, current_unit = current
    op, target_num, target_unit = target_expr
    if current_unit != target_unit:
        return "unknown"

    if op == ">=" and current_num >= target_num:
        return "meets_target"
    if op == ">" and current_num > target_num:
        return "meets_target"
    if op == "<=" and current_num <= target_num:
        return "meets_target"
    if op == "<" and current_num < target_num:
        return "meets_target"

    if op in {">=", ">"}:
        return "below_target"
    return "above_target"


def _load_metrics_payload(path_value: str, flag_name: str) -> dict[str, dict[str, str]]:
    payload_path = Path(path_value)
    if not payload_path.exists():
        raise SystemExit(f"missing {flag_name} file: {payload_path}")
    data = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid {flag_name}: top-level value must be an object")

    parsed: dict[str, dict[str, str]] = {}
    for kpi_id, payload in data.items():
        if not isinstance(payload, dict):
            raise SystemExit(f"invalid {flag_name}: KPI '{kpi_id}' must map to an object")
        parsed[kpi_id] = {
            "current_value": str(payload.get("current_value", "TODO")),
            "status": str(payload.get("status", "TODO")),
            "evidence_link": str(payload.get("evidence_link", "TODO")),
            "previous_value": str(payload.get("previous_value", "")),
        }
    return parsed


def _load_metrics(
    metrics_json: str | None, previous_metrics_json: str | None
) -> dict[str, dict[str, str]]:
    if metrics_json is None:
        return {}

    current = _load_metrics_payload(metrics_json, "--metrics-json")
    previous = (
        _load_metrics_payload(previous_metrics_json, "--previous-metrics-json")
        if previous_metrics_json
        else {}
    )

    merged: dict[str, dict[str, str]] = {}
    for kpi_id, payload in current.items():
        previous_value = payload["previous_value"]
        if not previous_value and kpi_id in previous:
            previous_value = previous[kpi_id].get("current_value", "")
        merged[kpi_id] = {
            "current_value": payload["current_value"],
            "delta": _format_delta(payload["current_value"], previous_value) if previous_value else "TODO",
            "status": payload["status"],
            "evidence_link": payload["evidence_link"],
        }
    return merged


def _baseline_kpi_ids(baseline: dict[str, Any]) -> list[str]:
    return [str(item.get("id", "unknown")) for item in baseline.get("kpis", [])]


def _missing_kpi_ids(baseline: dict[str, Any], metrics: dict[str, dict[str, str]]) -> list[str]:
    return [kpi_id for kpi_id in _baseline_kpi_ids(baseline) if kpi_id not in metrics]


def _validate_metrics_completeness(baseline: dict[str, Any], metrics: dict[str, dict[str, str]]) -> None:
    missing = _missing_kpi_ids(baseline, metrics)
    if missing:
        raise SystemExit(f"strict metrics check failed: missing KPI values for {missing}")


def _build_summary_payload(
    baseline: dict[str, Any], snapshot_date: str, metrics: dict[str, dict[str, str]], output_path: Path
) -> dict[str, Any]:
    baseline_ids = _baseline_kpi_ids(baseline)
    missing = _missing_kpi_ids(baseline, metrics)
    metric_entries = []
    target_eval_counts = {"meets_target": 0, "below_target": 0, "above_target": 0, "unknown": 0}

    for kpi in baseline.get("kpis", []):
        kpi_id = str(kpi.get("id", "unknown"))
        target = str(kpi.get("target", "unknown"))
        metric_data = metrics.get(kpi_id)
        current_value = metric_data["current_value"] if metric_data else "TODO"
        target_eval = _evaluate_target_status(current_value, target)
        target_eval_counts[target_eval] += 1
        metric_entries.append(
            {
                "id": kpi_id,
                "lane": str(kpi.get("lane", "unknown")),
                "target": target,
                "current_value": current_value,
                "delta": metric_data["delta"] if metric_data else "TODO",
                "status": metric_data["status"] if metric_data else "TODO",
                "evidence_link": metric_data["evidence_link"] if metric_data else "TODO",
                "covered": metric_data is not None,
                "target_eval": target_eval,
            }
        )
    return {
        "program": baseline.get("program", "unknown"),
        "dashboard": baseline.get("dashboard", "unknown"),
        "snapshot_date": snapshot_date,
        "baseline_kpi_count": len(baseline_ids),
        "provided_kpi_count": len(metrics),
        "coverage_ratio": len(metrics) / len(baseline_ids) if baseline_ids else 0.0,
        "missing_kpi_ids": missing,
        "target_eval_counts": target_eval_counts,
        "output_markdown": str(output_path),
        "kpis": metric_entries,
    }




def _breach_kpi_ids(summary: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for item in summary.get("kpis", []):
        if item.get("covered") and item.get("target_eval") in {"below_target", "above_target"}:
            ids.append(str(item.get("id", "unknown")))
    return ids

def _render_snapshot(
    baseline: dict[str, Any], snapshot_date: str, metrics: dict[str, dict[str, str]]
) -> str:
    lines: list[str] = []
    lines.append(f"# World-Class KPI Dashboard Weekly Snapshot — {snapshot_date}")
    lines.append("")
    lines.append("Generated from `docs/artifacts/world-class-kpi-dashboard-baseline.json`.")
    lines.append("")
    lines.append("## Snapshot metadata")
    lines.append("")
    lines.append(f"- Program: `{baseline.get('program', 'unknown')}`")
    lines.append(f"- Dashboard: `{baseline.get('dashboard', 'unknown')}`")
    lines.append(f"- Baseline version: `{baseline.get('version', 'unknown')}`")
    lines.append(f"- Snapshot window: `{baseline.get('snapshot_window', 'unknown')}`")
    lines.append(f"- Review cadence: `{baseline.get('review_cadence', 'unknown')}`")
    lines.append(f"- KPI coverage: `{len(metrics)}/{len(baseline.get('kpis', []))}` with provided metric values")
    lines.append("")
    lines.append("## KPI scorecard")
    lines.append("")
    lines.append("| KPI ID | Lane | KPI | Target | Current value | Delta vs previous | Status | Evidence link |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for kpi in baseline.get("kpis", []):
        kpi_id = str(kpi.get("id", "unknown"))
        metric_data = metrics.get(
            kpi_id,
            {
                "current_value": "TODO",
                "delta": "TODO",
                "status": "TODO",
                "evidence_link": "TODO",
            },
        )
        lines.append(
            "| {id} | {lane} | {metric} | `{target}` | {current_value} | {delta} | {status} | {evidence_link} |".format(
                id=kpi_id,
                lane=kpi.get("lane", "unknown"),
                metric=kpi.get("metric", "unknown"),
                target=kpi.get("target", "unknown"),
                current_value=metric_data["current_value"],
                delta=metric_data["delta"],
                status=metric_data["status"],
                evidence_link=metric_data["evidence_link"],
            )
        )
    lines.append("")
    lines.append("## Owners on duty")
    lines.append("")
    lines.append("| Lane | Primary owner | Backup owner |")
    lines.append("| --- | --- | --- |")
    for lane, owner_data in baseline.get("owners", {}).items():
        lane_label = lane.replace("_", " ").title()
        lines.append(
            f"| {lane_label} | {owner_data.get('primary', 'unknown')} | {owner_data.get('backup', 'unknown')} |"
        )
    lines.append("")
    lines.append("## Breach escalation")
    lines.append("")
    lines.append("- [ ] No KPI breached target for 2 consecutive snapshots.")
    lines.append("- [ ] If breached, incident owner and ETA are recorded.")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Trend deltas are auto-calculated from `--previous-metrics-json` when provided.")
    lines.append("- Inline `previous_value` in `--metrics-json` is also supported as a fallback.")
    lines.append("- Use `--strict-metrics` to fail generation when any baseline KPI is missing.")
    lines.append("- Use `--summary-json` to emit a machine-readable snapshot rollup with target evaluation and breach IDs.")
    lines.append("- TODO: Attach raw export links for CI/SCM/security data.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a weekly world-class KPI dashboard snapshot markdown from baseline JSON."
    )
    parser.add_argument(
        "--baseline-json",
        default="docs/artifacts/world-class-kpi-dashboard-baseline.json",
        help="Path to the machine-readable baseline JSON.",
    )
    parser.add_argument(
        "--metrics-json",
        default=None,
        help="Optional path to current KPI metric values keyed by KPI id.",
    )
    parser.add_argument(
        "--previous-metrics-json",
        default=None,
        help="Optional path to previous snapshot KPI values keyed by KPI id.",
    )
    parser.add_argument(
        "--strict-metrics",
        action="store_true",
        help="Fail if any KPI listed in baseline is missing from provided metrics.",
    )
    parser.add_argument(
        "--summary-json",
        default=None,
        help="Optional path to write machine-readable snapshot summary JSON.",
    )
    parser.add_argument(
        "--fail-on-target-breach",
        action="store_true",
        help="Fail if any covered KPI evaluates as below_target or above_target.",
    )
    parser.add_argument(
        "--snapshot-date",
        default=_default_snapshot_date(),
        help="Snapshot date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown file path. Defaults to docs/artifacts/world-class-kpi-dashboard-weekly-<date>.md",
    )
    ns = parser.parse_args()

    snapshot_date = _validate_snapshot_date(ns.snapshot_date)
    baseline_path = Path(ns.baseline_json)
    if not baseline_path.exists():
        raise SystemExit(f"missing baseline json: {baseline_path}")

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if not isinstance(baseline.get("kpis", []), list):
        raise SystemExit("invalid baseline json: 'kpis' must be a list")
    if not isinstance(baseline.get("owners", {}), dict):
        raise SystemExit("invalid baseline json: 'owners' must be an object")

    metrics = _load_metrics(ns.metrics_json, ns.previous_metrics_json)
    if ns.strict_metrics:
        _validate_metrics_completeness(baseline, metrics)

    output_path = Path(ns.output or f"docs/artifacts/world-class-kpi-dashboard-weekly-{snapshot_date}.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_snapshot(baseline, snapshot_date, metrics), encoding="utf-8")

    summary = _build_summary_payload(baseline, snapshot_date, metrics, output_path)
    breach_ids = _breach_kpi_ids(summary)
    summary["breach_kpi_ids"] = breach_ids

    if ns.summary_json:
        summary_path = Path(ns.summary_json)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if ns.fail_on_target_breach and breach_ids:
        raise SystemExit(f"target breach check failed: {breach_ids}")

    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
