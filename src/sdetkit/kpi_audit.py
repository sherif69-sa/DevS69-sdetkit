from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-kpi-audit.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_SECTION_HEADER = "# KPI audit (Day 27)"
_REQUIRED_SECTIONS = [
    "## Who should run Day 27",
    "## KPI contract",
    "## Metric baseline and current snapshot",
    "## Launch checklist",
    "## KPI scoring model",
    "## Execution evidence mode",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit kpi-audit --format json --strict",
    "python -m sdetkit kpi-audit --emit-pack-dir docs/artifacts/day27-kpi-pack --format json --strict",
    "python -m sdetkit kpi-audit --execute --evidence-dir docs/artifacts/day27-kpi-pack/evidence --format json --strict",
    "python scripts/check_day27_kpi_audit_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit kpi-audit --format json --strict",
    "python scripts/check_day27_kpi_audit_contract.py --skip-evidence",
]

_DEFAULT_BASELINE = {
    "stars_per_week": 8,
    "readme_ctr_percent": 2.8,
    "discussions_per_week": 3,
    "external_prs_per_week": 1,
}
_DEFAULT_CURRENT = {
    "stars_per_week": 13,
    "readme_ctr_percent": 4.6,
    "discussions_per_week": 6,
    "external_prs_per_week": 3,
}

_DAY27_DEFAULT_PAGE = """# KPI audit (Day 27)

Day 27 closes the conversion sprint by comparing baseline vs current KPI performance and publishing corrective actions.

## Who should run Day 27

- Maintainers validating weekly growth outcomes from Days 22-26.
- DevRel/community operators tracking traffic-to-contribution conversion.
- Engineering managers proving roadmap execution impact.

## KPI contract

A Day 27 pass requires side-by-side baseline and current snapshots for:

- `stars_per_week`
- `readme_ctr_percent`
- `discussions_per_week`
- `external_prs_per_week`

## Metric baseline and current snapshot

- Baseline path: `docs/artifacts/day27-kpi-pack/day27-kpi-baseline.json`
- Current path: `docs/artifacts/day27-kpi-pack/day27-kpi-current.json`
- Every metric must be numeric and non-negative.

## Launch checklist

```bash
python -m sdetkit kpi-audit --format json --strict
python -m sdetkit kpi-audit --emit-pack-dir docs/artifacts/day27-kpi-pack --format json --strict
python -m sdetkit kpi-audit --execute --evidence-dir docs/artifacts/day27-kpi-pack/evidence --format json --strict
python scripts/check_day27_kpi_audit_contract.py
```

## KPI scoring model

Day 27 computes weighted readiness score (0-100):

- Docs contract + command lane completeness: 45 points.
- Discoverability links in README/docs index: 20 points.
- Top-10 roadmap and KPI vocabulary alignment: 15 points.
- Baseline/current metric data validity: 20 points.

## Execution evidence mode

`--execute` runs deterministic Day 27 checks and writes logs to `--evidence-dir` for final closeout review.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_metrics(path: Path, fallback: dict[str, float]) -> tuple[dict[str, float], bool]:
    if not path.exists():
        return fallback.copy(), True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback.copy(), False

    out: dict[str, float] = {}
    for key in fallback:
        value = data.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            out[key] = float(value)
        else:
            return fallback.copy(), False
    return out, True


def _metric_deltas(
    baseline: dict[str, float], current: dict[str, float]
) -> dict[str, dict[str, float | str]]:
    rows: dict[str, dict[str, float | str]] = {}
    for key, base in baseline.items():
        curr = current[key]
        delta = curr - base
        pct = 0.0 if base == 0 else round((delta / base) * 100, 2)
        rows[key] = {
            "baseline": base,
            "current": curr,
            "delta": round(delta, 2),
            "delta_percent": pct,
            "trend": "up" if delta > 0 else ("flat" if delta == 0 else "down"),
        }
    return rows


def build_kpi_audit_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
    baseline_path: str = "docs/artifacts/day27-kpi-pack/day27-kpi-baseline.json",
    current_path: str = "docs/artifacts/day27-kpi-pack/day27-kpi-current.json",
) -> dict[str, Any]:
    page_path = root / docs_page_path
    page_text = _read(page_path)
    readme_text = _read(root / readme_path)
    docs_index_text = _read(root / docs_index_path)
    top10_text = _read(root / top10_path)

    missing_sections = [
        section for section in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if section not in page_text
    ]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]

    baseline, baseline_ok = _load_metrics(root / baseline_path, _DEFAULT_BASELINE)
    current, current_ok = _load_metrics(root / current_path, _DEFAULT_CURRENT)
    deltas = _metric_deltas(baseline, current)

    checks: list[dict[str, Any]] = [
        {
            "check_id": "docs_page_exists",
            "category": "contract",
            "weight": 10,
            "passed": page_path.exists(),
            "evidence": str(page_path),
        },
        {
            "check_id": "required_sections_present",
            "category": "contract",
            "weight": 20,
            "passed": not missing_sections,
            "evidence": {"missing_sections": missing_sections},
        },
        {
            "check_id": "required_commands_present",
            "category": "contract",
            "weight": 15,
            "passed": not missing_commands,
            "evidence": {"missing_commands": missing_commands},
        },
        {
            "check_id": "readme_day27_link",
            "category": "discoverability",
            "weight": 8,
            "passed": "docs/integrations-kpi-audit.md" in readme_text,
            "evidence": "docs/integrations-kpi-audit.md",
        },
        {
            "check_id": "readme_day27_command",
            "category": "discoverability",
            "weight": 6,
            "passed": "kpi-audit" in readme_text,
            "evidence": "kpi-audit",
        },
        {
            "check_id": "docs_index_day27_link",
            "category": "discoverability",
            "weight": 6,
            "passed": "day-27-ultra-upgrade-report.md" in docs_index_text,
            "evidence": "day-27-ultra-upgrade-report.md",
        },
        {
            "check_id": "top10_day27_alignment",
            "category": "strategy",
            "weight": 8,
            "passed": "Day 27 \u2014 KPI audit" in top10_text,
            "evidence": "Day 27 \u2014 KPI audit",
        },
        {
            "check_id": "docs_mentions_core_kpis",
            "category": "strategy",
            "weight": 7,
            "passed": all(
                marker in page_text
                for marker in [
                    "stars_per_week",
                    "readme_ctr_percent",
                    "discussions_per_week",
                    "external_prs_per_week",
                ]
            ),
            "evidence": "stars_per_week/readme_ctr_percent/discussions_per_week/external_prs_per_week",
        },
        {
            "check_id": "baseline_metrics_valid",
            "category": "data",
            "weight": 10,
            "passed": baseline_ok,
            "evidence": baseline_path,
        },
        {
            "check_id": "current_metrics_valid",
            "category": "data",
            "weight": 10,
            "passed": current_ok,
            "evidence": current_path,
        },
    ]

    failed = [item for item in checks if not item["passed"]]
    critical = {
        "docs_page_exists",
        "required_sections_present",
        "required_commands_present",
        "top10_day27_alignment",
        "baseline_metrics_valid",
        "current_metrics_valid",
    }
    critical_failures = [item["check_id"] for item in failed if item["check_id"] in critical]

    total_weight = sum(int(item["weight"]) for item in checks)
    earned_weight = sum(int(item["weight"]) for item in checks if item["passed"])
    score = round((earned_weight / total_weight) * 100, 2) if total_weight else 0.0

    recommendations: list[str] = []
    if missing_sections or missing_commands:
        recommendations.append("Restore Day 27 KPI docs contract and command lane before closeout.")
    if any(item["category"] == "discoverability" for item in failed):
        recommendations.append(
            "Add Day 27 KPI links and command examples in README/docs index for operator visibility."
        )
    if not baseline_ok or not current_ok:
        recommendations.append(
            "Provide valid numeric baseline/current KPI snapshots before strict KPI audit sign-off."
        )
    if not recommendations:
        recommendations.append(
            "Day 27 KPI audit lane is healthy; publish weekly KPI deltas and corrective actions."
        )

    return {
        "name": "day27-kpi-audit",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "baseline": baseline_path,
            "current": current_path,
        },
        "checks": checks,
        "metrics": {
            "baseline": baseline,
            "current": current,
            "deltas": deltas,
        },
        "summary": {
            "activation_score": score,
            "total_checks": len(checks),
            "failed_checks": [item["check_id"] for item in failed],
            "critical_failures": critical_failures,
            "recommendations": recommendations,
        },
    }


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Day 27 KPI audit summary",
        f"score={payload['summary']['activation_score']}",
        f"failed={','.join(payload['summary']['failed_checks']) or 'none'}",
        f"critical={','.join(payload['summary']['critical_failures']) or 'none'}",
        "",
        "KPI deltas:",
    ]
    for key, row in payload["metrics"]["deltas"].items():
        lines.append(
            f"- {key}: baseline={row['baseline']} current={row['current']} delta={row['delta']} ({row['delta_percent']}%), trend={row['trend']}"
        )
    return "\n".join(lines)


def emit_pack(root: Path, out_dir: Path, payload: dict[str, Any]) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "day27-kpi-summary.json"
    scorecard = out_dir / "day27-kpi-scorecard.md"
    delta_table = out_dir / "day27-kpi-delta-table.md"
    action_plan = out_dir / "day27-kpi-corrective-actions.md"
    validation = out_dir / "day27-validation-commands.md"
    baseline = out_dir / "day27-kpi-baseline.json"
    current = out_dir / "day27-kpi-current.json"

    summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scorecard.write_text(_render_text(payload) + "\n", encoding="utf-8")

    rows = [
        "# Day 27 KPI delta table",
        "",
        "| KPI | Baseline | Current | Delta | Delta % | Trend |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for key, row in payload["metrics"]["deltas"].items():
        rows.append(
            f"| {key} | {row['baseline']} | {row['current']} | {row['delta']} | {row['delta_percent']}% | {row['trend']} |"
        )
    delta_table.write_text("\n".join(rows) + "\n", encoding="utf-8")

    action_plan.write_text(
        "\n".join(
            [
                "# Day 27 KPI corrective action plan",
                "",
                "## Priority lane",
                "- [ ] Keep positive KPI deltas stable through Day 28 weekly review.",
                "- [ ] Escalate any KPI with flat/down trend to an owner and due date.",
                "- [ ] Publish weekly KPI narrative (what changed, why, next action).",
                "",
                "## Suggested owners",
                "- Growth owner: README CTR + stars/week",
                "- Community owner: discussions/week",
                "- Maintainer owner: external PRs/week",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    validation.write_text(
        "\n".join(["# Day 27 validation commands", "", "```bash", *_REQUIRED_COMMANDS, "```"])
        + "\n",
        encoding="utf-8",
    )
    baseline.write_text(
        json.dumps(payload["metrics"]["baseline"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    current.write_text(
        json.dumps(payload["metrics"]["current"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return [
        str(path.relative_to(root))
        for path in [summary, scorecard, delta_table, action_plan, validation, baseline, current]
    ]


def execute_commands(root: Path, evidence_dir: Path, timeout_sec: int) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for command in _EXECUTION_COMMANDS:
        argv = shlex.split(command)
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        proc = subprocess.run(argv, cwd=root, text=True, capture_output=True, timeout=timeout_sec)
        results.append(
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )

    payload = {
        "name": "day27-kpi-audit-execution",
        "total_commands": len(_EXECUTION_COMMANDS),
        "results": results,
    }
    (evidence_dir / "day27-execution-summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit kpi-audit", description="Day 27 KPI audit closeout lane."
    )
    parser.add_argument("--root", default=".", help="Repository root path.")
    parser.add_argument(
        "--readme", default="README.md", help="README path for discoverability checks."
    )
    parser.add_argument(
        "--docs-index", default="docs/index.md", help="Docs index path for discoverability checks."
    )
    parser.add_argument("--top10", default=_TOP10_PATH, help="Top-10 roadmap strategy path.")
    parser.add_argument(
        "--baseline",
        default="docs/artifacts/day27-kpi-pack/day27-kpi-baseline.json",
        help="Baseline KPI snapshot JSON.",
    )
    parser.add_argument(
        "--current",
        default="docs/artifacts/day27-kpi-pack/day27-kpi-current.json",
        help="Current KPI snapshot JSON.",
    )
    parser.add_argument(
        "--write-defaults", action="store_true", help="Create default Day 27 integration page."
    )
    parser.add_argument(
        "--emit-pack-dir", default="", help="Optional output directory for generated Day 27 files."
    )
    parser.add_argument(
        "--execute", action="store_true", help="Run Day 27 command chain and emit evidence logs."
    )
    parser.add_argument(
        "--evidence-dir",
        default="docs/artifacts/day27-kpi-pack/evidence",
        help="Output directory for execution evidence logs.",
    )
    parser.add_argument(
        "--timeout-sec", type=int, default=120, help="Per-command timeout used by --execute."
    )
    parser.add_argument(
        "--min-score", type=float, default=90.0, help="Minimum score for strict pass."
    )
    parser.add_argument(
        "--strict", action="store_true", help="Fail when score or critical checks are not ready."
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()
    page = root / _PAGE_PATH

    if ns.write_defaults:
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(_DAY27_DEFAULT_PAGE, encoding="utf-8")

    payload = build_kpi_audit_summary(
        root,
        readme_path=ns.readme,
        docs_index_path=ns.docs_index,
        top10_path=ns.top10,
        baseline_path=ns.baseline,
        current_path=ns.current,
    )
    page_text = _read(page)
    missing_sections = [
        section for section in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if section not in page_text
    ]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]
    payload["strict_failures"] = [*missing_sections, *missing_commands]

    if ns.emit_pack_dir:
        payload["emitted_pack_files"] = emit_pack(root, root / ns.emit_pack_dir, payload)
    if ns.execute:
        payload["execution"] = execute_commands(root, root / ns.evidence_dir, ns.timeout_sec)

    strict_failed = (
        bool(payload["strict_failures"])
        or payload["summary"]["activation_score"] < ns.min_score
        or bool(payload["summary"]["critical_failures"])
    )

    if ns.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and strict_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
