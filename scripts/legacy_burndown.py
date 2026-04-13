from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _load_report(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"legacy report must be a JSON object: {path}"
        raise ValueError(msg)
    return raw


def _resolve_baseline_from_history(current_path: Path, history_dir: Path) -> Path | None:
    if not history_dir.exists():
        return None
    candidates = sorted(
        (p for p in history_dir.glob("*.json") if p.resolve() != current_path.resolve()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _domain_from_path(path: str) -> str:
    head = path.split("/", 1)[0]
    if head in {"docs", "scripts", "src", "tests", "examples", "templates", "plans"}:
        return head
    return "other"


def _build_groups(findings: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    by_category: Counter[str] = Counter()
    by_path: Counter[str] = Counter()
    by_domain: Counter[str] = Counter()
    for finding in findings:
        command = str(finding.get("command", ""))
        category = command.split("-", 1)[0] if command else "unknown"
        path = str(finding.get("path", ""))
        path_group = path.rsplit("/", 1)[0] if "/" in path else "."
        by_category[category] += 1
        by_path[path_group] += 1
        by_domain[_domain_from_path(path)] += 1
    return {
        "category": dict(sorted(by_category.items())),
        "path": dict(sorted(by_path.items())),
        "domain": dict(sorted(by_domain.items())),
    }


def _calc_delta(current: int, baseline: int) -> dict[str, float | int]:
    delta = current - baseline
    reduction = baseline - current
    reduction_pct = 0.0 if baseline <= 0 else (reduction / baseline) * 100.0
    return {
        "baseline": baseline,
        "current": current,
        "delta": delta,
        "reduction_pct": round(reduction_pct, 3),
    }


def _build_summary(payload: dict[str, Any]) -> str:
    delta = payload["totals"]
    status = "on-track" if payload["weekly_kpi"]["target_met"] else "behind"
    lines = [
        "# Legacy burn-down weekly summary",
        "",
        f"- Baseline findings: **{delta['baseline']}**",
        f"- Current findings: **{delta['current']}**",
        f"- Delta: **{delta['delta']}**",
        f"- Reduction: **{delta['reduction_pct']}%**",
        (
            f"- KPI target: **{payload['weekly_kpi']['target_reduction_pct']}%** "
            f"(status: **{status}**)"
        ),
        "",
        "## Grouped findings",
    ]
    for group_name, counts in payload["groups"]["current"].items():
        lines.append(f"### {group_name.title()}")
        if not counts:
            lines.append("- none")
            continue
        for key, value in counts.items():
            lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def _build_csv(payload: dict[str, Any]) -> str:
    totals = payload["totals"]
    kpi = payload["weekly_kpi"]
    rows = [
        "metric,value",
        f"baseline,{totals['baseline']}",
        f"current,{totals['current']}",
        f"delta,{totals['delta']}",
        f"reduction_pct,{totals['reduction_pct']}",
        f"target_reduction_pct,{kpi['target_reduction_pct']}",
        f"target_met,{str(kpi['target_met']).lower()}",
    ]
    return "\n".join(rows) + "\n"


def _findings_list(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in findings:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def build_burndown(
    current: dict[str, Any], baseline: dict[str, Any] | None, target_reduction_pct: float
) -> dict[str, Any]:
    current_findings = _findings_list(current)
    baseline_findings = _findings_list(baseline)
    current_count = int(current.get("count", len(current_findings)))
    baseline_count = (
        int(baseline.get("count", len(baseline_findings)))
        if isinstance(baseline, dict)
        else current_count
    )
    totals = _calc_delta(current_count, baseline_count)
    return {
        "schema_version": "1",
        "source_contract": "sdetkit.legacy.burndown.v1",
        "totals": totals,
        "weekly_kpi": {
            "target_reduction_pct": round(target_reduction_pct, 3),
            "target_met": totals["reduction_pct"] >= target_reduction_pct,
        },
        "groups": {
            "current": _build_groups(current_findings),
            "baseline": _build_groups(baseline_findings),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/legacy_burndown.py")
    parser.add_argument("--current", default=".sdetkit/out/legacy-command-analyzer.json")
    parser.add_argument("--baseline")
    parser.add_argument("--baseline-from-history")
    parser.add_argument("--target-reduction-pct", type=float, default=10.0)
    parser.add_argument("--json-out", default=".sdetkit/out/legacy-burndown.json")
    parser.add_argument("--md-out", default=".sdetkit/out/legacy-burndown.md")
    parser.add_argument("--csv-out", default=".sdetkit/out/legacy-burndown.csv")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(argv)

    current_path = Path(ns.current)
    current = _load_report(current_path)
    baseline_path: Path | None = Path(ns.baseline) if ns.baseline else None
    if baseline_path is None and ns.baseline_from_history:
        baseline_path = _resolve_baseline_from_history(
            current_path=current_path,
            history_dir=Path(ns.baseline_from_history),
        )
    baseline = _load_report(baseline_path) if baseline_path else None
    payload = build_burndown(current, baseline, float(ns.target_reduction_pct))
    if baseline_path:
        payload["baseline_source"] = str(baseline_path)

    json_out = Path(ns.json_out)
    md_out = Path(ns.md_out)
    csv_out = Path(ns.csv_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_out.write_text(_build_summary(payload), encoding="utf-8")
    csv_out.write_text(_build_csv(payload), encoding="utf-8")

    if ns.format == "json":
        print(json.dumps(payload, sort_keys=True))
    else:
        print(
            f"legacy-burndown: current={payload['totals']['current']} baseline={payload['totals']['baseline']}"
        )
        print(
            f"legacy-burndown: reduction={payload['totals']['reduction_pct']}% target={payload['weekly_kpi']['target_reduction_pct']}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
