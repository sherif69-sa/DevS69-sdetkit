from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return round(current - previous, 3)


def _build_report(
    *,
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    week_label: str,
) -> dict[str, Any]:
    current_metrics = {
        "time_to_first_success_minutes": _safe_float(current.get("time_to_first_success_minutes")),
        "lint_debt_count": _safe_float(current.get("lint_debt_count")),
        "type_debt_count": _safe_float(current.get("type_debt_count")),
        "ci_cycle_minutes": _safe_float(current.get("ci_cycle_minutes")),
        "release_gate_pass_rate": _safe_float(current.get("release_gate_pass_rate")),
    }

    previous_metrics: dict[str, float | None] = {}
    if previous is not None:
        prev_values = previous.get("metrics", {}) if isinstance(previous.get("metrics", {}), dict) else {}
        previous_metrics = {
            "time_to_first_success_minutes": _safe_float(prev_values.get("time_to_first_success_minutes")),
            "lint_debt_count": _safe_float(prev_values.get("lint_debt_count")),
            "type_debt_count": _safe_float(prev_values.get("type_debt_count")),
            "ci_cycle_minutes": _safe_float(prev_values.get("ci_cycle_minutes")),
            "release_gate_pass_rate": _safe_float(prev_values.get("release_gate_pass_rate")),
        }

    trends = {
        key: {
            "previous": previous_metrics.get(key),
            "current": value,
            "delta": _compute_delta(value, previous_metrics.get(key)),
        }
        for key, value in current_metrics.items()
    }

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "week": week_label,
        "metrics": current_metrics,
        "trends": trends,
        "source": {
            "current_input": current.get("_source_path"),
            "previous_input": previous.get("_source_path") if previous else None,
        },
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Release Confidence KPI Pack",
        "",
        f"- Week: `{payload['week']}`",
        f"- Generated at: `{payload['generated_at']}`",
        "",
        "| KPI | Previous | Current | Delta |",
        "| --- | --- | --- | --- |",
    ]

    label_map = {
        "time_to_first_success_minutes": "Time to first success (minutes)",
        "lint_debt_count": "Lint debt count",
        "type_debt_count": "Type debt count",
        "ci_cycle_minutes": "CI cycle (minutes)",
        "release_gate_pass_rate": "Release gate pass rate",
    }
    for key, label in label_map.items():
        trend = payload["trends"][key]
        lines.append(
            f"| {label} | {trend['previous']} | {trend['current']} | {trend['delta']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build weekly release-confidence KPI pack artifacts.")
    parser.add_argument("--current", required=True, help="Path to JSON with current KPI values.")
    parser.add_argument("--previous", default=None, help="Optional previous KPI summary JSON for trend delta.")
    parser.add_argument("--week", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--out-json", default="build/release-confidence-kpi-pack.json")
    parser.add_argument("--out-md", default="build/release-confidence-kpi-pack.md")
    ns = parser.parse_args(argv)

    current_path = Path(ns.current)
    current = _read_json(current_path)
    if current is None:
        raise SystemExit(f"Invalid current KPI input: {current_path}")
    current["_source_path"] = str(current_path)

    previous: dict[str, Any] | None = None
    if ns.previous:
        previous_path = Path(ns.previous)
        loaded = _read_json(previous_path)
        if loaded is not None:
            loaded["_source_path"] = str(previous_path)
            previous = loaded

    payload = _build_report(current=current, previous=previous, week_label=ns.week)

    out_json = Path(ns.out_json)
    out_md = Path(ns.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
