from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day35-kpi-instrumentation.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY34_SUMMARY_PATH = "docs/artifacts/day34-demo-asset2-pack/day34-demo-asset2-summary.json"
_DAY34_BOARD_PATH = "docs/artifacts/day34-demo-asset2-pack/day34-delivery-board.md"
_SECTION_HEADER = "# Day 35 \u2014 KPI instrumentation closeout"
_REQUIRED_SECTIONS = [
    "## Why Day 35 matters",
    "## Required inputs (Day 34)",
    "## Day 35 command lane",
    "## KPI instrumentation contract",
    "## KPI quality checklist",
    "## Day 35 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day35-kpi-instrumentation --format json --strict",
    "python -m sdetkit day35-kpi-instrumentation --emit-pack-dir docs/artifacts/day35-kpi-instrumentation-pack --format json --strict",
    "python -m sdetkit day35-kpi-instrumentation --execute --evidence-dir docs/artifacts/day35-kpi-instrumentation-pack/evidence --format json --strict",
    "python scripts/check_day35_kpi_instrumentation_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day35-kpi-instrumentation --format json --strict",
    "python -m sdetkit day35-kpi-instrumentation --emit-pack-dir docs/artifacts/day35-kpi-instrumentation-pack --format json --strict",
    "python scripts/check_day35_kpi_instrumentation_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for KPI instrumentation maintenance.",
    "Metric taxonomy includes acquisition, activation, retention, and reliability slices.",
    "Every KPI has source command, cadence, owner, and threshold fields documented.",
    "Day 35 report links KPI drift to at least three concrete next-week actions.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes at least eight KPIs split across acquisition/activation/retention/reliability",
    "- [ ] Every KPI row has source command and refresh cadence",
    "- [ ] At least three threshold alerts are documented with owner + escalation action",
    "- [ ] Weekly review delta compares current week vs prior week in percentages",
    "- [ ] Artifact pack includes dashboard, alert policy, and narrative summary",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 35 KPI dictionary committed",
    "- [ ] Day 35 dashboard snapshot exported",
    "- [ ] Day 35 alert policy reviewed with owner + backup",
    "- [ ] Day 36 distribution message references KPI shifts",
    "- [ ] Day 37 experiment backlog seeded from KPI misses",
]

_DAY35_DEFAULT_PAGE = """# Day 35 \u2014 KPI instrumentation closeout

Day 35 closes the instrumentation lane by converting demo activity into measurable weekly signals and next-week actions.

## Why Day 35 matters

- Turns demo outputs into a durable KPI operating loop.
- Reduces attribution gaps by forcing explicit metric sources and cadence.
- Upgrades weekly review quality from narrative-only updates to threshold-backed decisions.

## Required inputs (Day 34)

- `docs/artifacts/day34-demo-asset2-pack/day34-demo-asset2-summary.json`
- `docs/artifacts/day34-demo-asset2-pack/day34-delivery-board.md`

## Day 35 command lane

```bash
python -m sdetkit day35-kpi-instrumentation --format json --strict
python -m sdetkit day35-kpi-instrumentation --emit-pack-dir docs/artifacts/day35-kpi-instrumentation-pack --format json --strict
python -m sdetkit day35-kpi-instrumentation --execute --evidence-dir docs/artifacts/day35-kpi-instrumentation-pack/evidence --format json --strict
python scripts/check_day35_kpi_instrumentation_contract.py
```

## KPI instrumentation contract

- Single owner + backup reviewer are assigned for KPI instrumentation maintenance.
- Metric taxonomy includes acquisition, activation, retention, and reliability slices.
- Every KPI has source command, cadence, owner, and threshold fields documented.
- Day 35 report links KPI drift to at least three concrete next-week actions.

## KPI quality checklist

- [ ] Includes at least eight KPIs split across acquisition/activation/retention/reliability
- [ ] Every KPI row has source command and refresh cadence
- [ ] At least three threshold alerts are documented with owner + escalation action
- [ ] Weekly review delta compares current week vs prior week in percentages
- [ ] Artifact pack includes dashboard, alert policy, and narrative summary

## Day 35 delivery board

- [ ] Day 35 KPI dictionary committed
- [ ] Day 35 dashboard snapshot exported
- [ ] Day 35 alert policy reviewed with owner + backup
- [ ] Day 36 distribution message references KPI shifts
- [ ] Day 37 experiment backlog seeded from KPI misses

## Scoring model

Day 35 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 34 continuity and strict baseline carryover: 35 points.
- KPI contract lock + delivery board readiness: 15 points.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _load_day34(path: Path) -> tuple[float, bool, int]:
    data = _load_json(path)
    if data is None:
        return 0.0, False, 0
    summary = data.get("summary")
    checks = data.get("checks")
    score = summary.get("activation_score") if isinstance(summary, dict) else None
    strict_pass = summary.get("strict_pass") if isinstance(summary, dict) else False
    check_count = len(checks) if isinstance(checks, list) else 0
    resolved_score = float(score) if isinstance(score, (int, float)) else 0.0
    return resolved_score, bool(strict_pass), check_count


def _board_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    lines = [line.strip().lower() for line in text.splitlines()]
    item_count = sum(1 for line in lines if line.startswith("- [ ]"))
    has_day35 = any("day 35" in line for line in lines)
    has_day36 = any("day 36" in line for line in lines)
    return item_count, has_day35, has_day36


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_day35_kpi_instrumentation_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
) -> dict[str, Any]:
    page_path = root / docs_page_path
    page_text = _read(page_path)
    readme_text = _read(root / readme_path)
    docs_index_text = _read(root / docs_index_path)
    top10_text = _read(root / top10_path)

    missing_sections = [s for s in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if s not in page_text]
    missing_commands = [c for c in _REQUIRED_COMMANDS if c not in page_text]
    missing_contract_lines = _contains_all_lines(
        page_text, [f"- {line}" for line in _REQUIRED_CONTRACT_LINES]
    )
    missing_quality_lines = _contains_all_lines(page_text, _REQUIRED_QUALITY_LINES)
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    day34_summary = root / _DAY34_SUMMARY_PATH
    day34_board = root / _DAY34_BOARD_PATH
    day34_score, day34_strict, day34_check_count = _load_day34(day34_summary)
    board_count, board_has_day35, board_has_day36 = _board_stats(day34_board)

    checks: list[dict[str, Any]] = [
        {
            "check_id": "docs_page_exists",
            "weight": 10,
            "passed": page_path.exists(),
            "evidence": str(page_path),
        },
        {
            "check_id": "required_sections_present",
            "weight": 10,
            "passed": not missing_sections,
            "evidence": {"missing_sections": missing_sections},
        },
        {
            "check_id": "required_commands_present",
            "weight": 10,
            "passed": not missing_commands,
            "evidence": {"missing_commands": missing_commands},
        },
        {
            "check_id": "readme_day35_link",
            "weight": 8,
            "passed": "docs/integrations-day35-kpi-instrumentation.md" in readme_text,
            "evidence": "docs/integrations-day35-kpi-instrumentation.md",
        },
        {
            "check_id": "readme_day35_command",
            "weight": 4,
            "passed": "day35-kpi-instrumentation" in readme_text,
            "evidence": "day35-kpi-instrumentation",
        },
        {
            "check_id": "docs_index_day35_links",
            "weight": 8,
            "passed": (
                "day-35-big-upgrade-report.md" in docs_index_text
                and "integrations-day35-kpi-instrumentation.md" in docs_index_text
            ),
            "evidence": "day-35-big-upgrade-report.md + integrations-day35-kpi-instrumentation.md",
        },
        {
            "check_id": "top10_day35_alignment",
            "weight": 5,
            "passed": ("Day 35" in top10_text and "Day 36" in top10_text),
            "evidence": "Day 35 + Day 36 strategy chain",
        },
        {
            "check_id": "day34_summary_present",
            "weight": 10,
            "passed": day34_summary.exists(),
            "evidence": str(day34_summary),
        },
        {
            "check_id": "day34_delivery_board_present",
            "weight": 8,
            "passed": day34_board.exists(),
            "evidence": str(day34_board),
        },
        {
            "check_id": "day34_quality_floor",
            "weight": 10,
            "passed": day34_strict and day34_score >= 95,
            "evidence": {
                "day34_score": day34_score,
                "strict_pass": day34_strict,
                "day34_checks": day34_check_count,
            },
        },
        {
            "check_id": "day34_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day35 and board_has_day36,
            "evidence": {
                "board_items": board_count,
                "contains_day35": board_has_day35,
                "contains_day36": board_has_day36,
            },
        },
        {
            "check_id": "kpi_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "kpi_quality_checklist_locked",
            "weight": 3,
            "passed": not missing_quality_lines,
            "evidence": {"missing_quality_items": missing_quality_lines},
        },
        {
            "check_id": "delivery_board_locked",
            "weight": 2,
            "passed": not missing_board_items,
            "evidence": {"missing_board_items": missing_board_items},
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    critical_failures: list[str] = []
    if not day34_summary.exists() or not day34_board.exists():
        critical_failures.append("day34_handoff_inputs")
    if not day34_strict:
        critical_failures.append("day34_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day34_strict:
        wins.append(f"Day 34 continuity is strict-pass with activation score={day34_score}.")
    else:
        misses.append("Day 34 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 34 demo asset #2 command and restore strict pass baseline before Day 35 lock."
        )

    if board_count >= 5 and board_has_day35 and board_has_day36:
        wins.append(
            f"Day 34 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 34 delivery board integrity is incomplete (needs >=5 items and Day 35/36 anchors)."
        )
        handoff_actions.append(
            "Repair Day 34 delivery board entries to include Day 35 and Day 36 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "KPI instrumentation contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append("KPI contract, quality checklist, or delivery board entries are missing.")
        handoff_actions.append(
            "Complete all Day 35 KPI contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 35 KPI instrumentation closeout is fully complete and ready for Day 36 distribution execution."
        )

    return {
        "name": "day35-kpi-instrumentation",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day34_summary": str(day34_summary.relative_to(root))
            if day34_summary.exists()
            else str(day34_summary),
            "day34_delivery_board": str(day34_board.relative_to(root))
            if day34_board.exists()
            else str(day34_board),
        },
        "checks": checks,
        "rollup": {
            "day34_activation_score": day34_score,
            "day34_checks": day34_check_count,
            "day34_delivery_board_items": board_count,
        },
        "summary": {
            "activation_score": score,
            "passed_checks": len(checks) - len(failed),
            "failed_checks": len(failed),
            "critical_failures": critical_failures,
            "strict_pass": not failed and not critical_failures,
        },
        "wins": wins,
        "misses": misses,
        "handoff_actions": handoff_actions,
    }


def _to_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return (
        "Day 35 KPI instrumentation summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Day 35 KPI instrumentation summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## Day 34 continuity",
        "",
        f"- Day 34 activation score: `{payload['rollup']['day34_activation_score']}`",
        f"- Day 34 checks evaluated: `{payload['rollup']['day34_checks']}`",
        f"- Day 34 delivery board checklist items: `{payload['rollup']['day34_delivery_board_items']}`",
        "",
        "## Wins",
    ]
    lines.extend(f"- {item}" for item in payload["wins"])
    lines.append("\n## Misses")
    lines.extend(f"- {item}" for item in payload["misses"] or ["No misses recorded."])
    lines.append("\n## Handoff actions")
    lines.extend(
        f"- [ ] {item}" for item in payload["handoff_actions"] or ["No handoff actions required."]
    )
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _emit_pack(root: Path, payload: dict[str, Any], pack_dir: Path) -> None:
    target = (root / pack_dir).resolve() if not pack_dir.is_absolute() else pack_dir
    target.mkdir(parents=True, exist_ok=True)
    _write(target / "day35-kpi-instrumentation-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day35-kpi-instrumentation-summary.md", _to_markdown(payload))
    _write(
        target / "day35-kpi-dictionary.csv",
        "metric,segment,source_command,cadence,owner,threshold,notes\n"
        "docs_unique_visitors,acquisition,python -m sdetkit report --input docs/traffic.json --format json,daily,growth-owner,>=1500,Docs traffic stability\n"
        "readme_to_command_ctr,activation,python -m sdetkit proof --json,daily,growth-owner,>=12%,README conversion\n"
        "first_successful_run_rate,activation,python -m sdetkit doctor --json,weekly,qa-owner,>=85%,Onboarding quality\n"
        "returning_users_7d,retention,python -m sdetkit report --input analytics.json --format json,weekly,pm-owner,>=25%,Retention baseline\n"
        "discussion_reply_time_hours,reliability,python -m sdetkit ops status --format json,daily,community-owner,<=24,Community latency\n"
        "ci_flake_rate,reliability,python -m sdetkit repo audit --json,daily,eng-owner,<=3%,Stability\n"
        "release_cadence_adherence,reliability,python -m sdetkit release-readiness-board --json,weekly,release-owner,>=95%,Cadence health\n"
        "external_pr_conversion,retention,python -m sdetkit contributor-funnel --format json,weekly,community-owner,>=8%,PR funnel health\n",
    )
    _write(
        target / "day35-alert-policy.md",
        "# Day 35 alert policy\n\n"
        "- `readme_to_command_ctr < 10%` for two consecutive days -> owner opens remediation issue within 24h.\n"
        "- `ci_flake_rate > 3%` on daily sweep -> block release tagging until flaky tests triaged.\n"
        "- `discussion_reply_time_hours > 24` for 3+ threads -> trigger backup reviewer support shift.\n",
    )
    _write(
        target / "day35-delivery-board.md",
        "# Day 35 delivery board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day35-validation-commands.md",
        "# Day 35 validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
    )


def _run_execution(root: Path, evidence_dir: Path) -> None:
    target = (root / evidence_dir).resolve() if not evidence_dir.is_absolute() else evidence_dir
    target.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    for command in _EXECUTION_COMMANDS:
        argv = shlex.split(command)
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        proc = subprocess.run(argv, cwd=root, text=True, capture_output=True, check=False)
        logs.append(
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
    summary = {
        "name": "day35-kpi-instrumentation-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "day35-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 35 KPI instrumentation closeout scorer.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--write-defaults", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.write_defaults:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DAY35_DEFAULT_PAGE)

    payload = build_day35_kpi_instrumentation_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day35-kpi-instrumentation-pack/evidence")
        )
        _run_execution(root, ev_dir)

    if ns.format == "json":
        rendered = json.dumps(payload, indent=2) + "\n"
    elif ns.format == "markdown":
        rendered = _to_markdown(payload)
    else:
        rendered = _to_text(payload)

    if ns.output:
        _write(
            (root / ns.output).resolve() if not Path(ns.output).is_absolute() else Path(ns.output),
            rendered,
        )
    else:
        print(rendered, end="")

    if ns.strict and (
        payload["summary"]["failed_checks"] > 0 or payload["summary"]["critical_failures"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
