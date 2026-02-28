from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day41-expansion-automation.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY40_SUMMARY_PATH = "docs/artifacts/day40-scale-lane-pack/day40-scale-lane-summary.json"
_DAY40_BOARD_PATH = "docs/artifacts/day40-scale-lane-pack/day40-delivery-board.md"
_SECTION_HEADER = "# Day 41 \u2014 Expansion automation lane"
_REQUIRED_SECTIONS = [
    "## Why Day 41 matters",
    "## Required inputs (Day 40)",
    "## Day 41 command lane",
    "## Expansion automation contract",
    "## Expansion quality checklist",
    "## Day 41 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day41-expansion-automation --format json --strict",
    "python -m sdetkit day41-expansion-automation --emit-pack-dir docs/artifacts/day41-expansion-automation-pack --format json --strict",
    "python -m sdetkit day41-expansion-automation --execute --evidence-dir docs/artifacts/day41-expansion-automation-pack/evidence --format json --strict",
    "python scripts/check_day41_expansion_automation_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day41-expansion-automation --format json --strict",
    "python -m sdetkit day41-expansion-automation --emit-pack-dir docs/artifacts/day41-expansion-automation-pack --format json --strict",
    "python scripts/check_day41_expansion_automation_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 41 expansion lane execution and KPI follow-up.",
    "The Day 41 expansion lane references Day 40 scale winners and misses with deterministic remediation loops.",
    "Every Day 41 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.",
    "Day 41 closeout records expansion learnings and Day 42 optimization priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes automation summary, expansion play matrix, and rollback strategy",
    "- [ ] Every section has owner, publish window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes expansion plan, automation matrix, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 41 expansion plan draft committed",
    "- [ ] Day 41 review notes captured with owner + backup",
    "- [ ] Day 41 automation matrix exported",
    "- [ ] Day 41 KPI scorecard snapshot exported",
    "- [ ] Day 42 optimization priorities drafted from Day 41 learnings",
]

_DAY41_DEFAULT_PAGE = """# Day 41 \u2014 Expansion automation lane

Day 41 closes with a major expansion automation upgrade that converts Day 40 scale evidence into repeatable workflows.

## Why Day 41 matters

- Converts Day 40 scale wins into automation-first operating motion.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from expansion outcomes into Day 42 optimization priorities.

## Required inputs (Day 40)

- `docs/artifacts/day40-scale-lane-pack/day40-scale-lane-summary.json`
- `docs/artifacts/day40-scale-lane-pack/day40-delivery-board.md`

## Day 41 command lane

```bash
python -m sdetkit day41-expansion-automation --format json --strict
python -m sdetkit day41-expansion-automation --emit-pack-dir docs/artifacts/day41-expansion-automation-pack --format json --strict
python -m sdetkit day41-expansion-automation --execute --evidence-dir docs/artifacts/day41-expansion-automation-pack/evidence --format json --strict
python scripts/check_day41_expansion_automation_contract.py
```

## Expansion automation contract

- Single owner + backup reviewer are assigned for Day 41 expansion lane execution and KPI follow-up.
- The Day 41 expansion lane references Day 40 scale winners and misses with deterministic remediation loops.
- Every Day 41 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Day 41 closeout records expansion learnings and Day 42 optimization priorities.

## Expansion quality checklist

- [ ] Includes automation summary, expansion play matrix, and rollback strategy
- [ ] Every section has owner, publish window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes expansion plan, automation matrix, KPI scorecard, and execution log

## Day 41 delivery board

- [ ] Day 41 expansion plan draft committed
- [ ] Day 41 review notes captured with owner + backup
- [ ] Day 41 automation matrix exported
- [ ] Day 41 KPI scorecard snapshot exported
- [ ] Day 42 optimization priorities drafted from Day 41 learnings

## Scoring model

Day 41 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 40 continuity and strict baseline carryover: 35 points.
- Expansion contract lock + delivery board readiness: 15 points.
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


def _load_day40(path: Path) -> tuple[float, bool, int]:
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
    items = [line for line in text.splitlines() if line.strip().startswith("- [")]
    return len(items), "Day 40" in text, "Day 41" in text


def _contains_all_lines(text: str, expected: list[str]) -> list[str]:
    return [line for line in expected if line not in text]


def build_day41_expansion_automation_summary(root: Path) -> dict[str, Any]:
    page_path = root / _PAGE_PATH
    readme_path = "README.md"
    docs_index_path = "docs/index.md"
    docs_page_path = _PAGE_PATH
    top10_path = _TOP10_PATH

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

    day40_summary = root / _DAY40_SUMMARY_PATH
    day40_board = root / _DAY40_BOARD_PATH
    day40_score, day40_strict, day40_check_count = _load_day40(day40_summary)
    board_count, board_has_day40, board_has_day41 = _board_stats(day40_board)

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
            "check_id": "readme_day41_link",
            "weight": 8,
            "passed": "docs/integrations-day41-expansion-automation.md" in readme_text,
            "evidence": "docs/integrations-day41-expansion-automation.md",
        },
        {
            "check_id": "readme_day41_command",
            "weight": 4,
            "passed": "day41-expansion-automation" in readme_text,
            "evidence": "day41-expansion-automation",
        },
        {
            "check_id": "docs_index_day41_links",
            "weight": 8,
            "passed": (
                "day-41-big-upgrade-report.md" in docs_index_text
                and "integrations-day41-expansion-automation.md" in docs_index_text
            ),
            "evidence": "day-41-big-upgrade-report.md + integrations-day41-expansion-automation.md",
        },
        {
            "check_id": "top10_day41_alignment",
            "weight": 5,
            "passed": ("Day 41" in top10_text and "Day 42" in top10_text),
            "evidence": "Day 41 + Day 42 strategy chain",
        },
        {
            "check_id": "day40_summary_present",
            "weight": 10,
            "passed": day40_summary.exists(),
            "evidence": str(day40_summary),
        },
        {
            "check_id": "day40_delivery_board_present",
            "weight": 8,
            "passed": day40_board.exists(),
            "evidence": str(day40_board),
        },
        {
            "check_id": "day40_quality_floor",
            "weight": 10,
            "passed": day40_strict and day40_score >= 95,
            "evidence": {
                "day40_score": day40_score,
                "strict_pass": day40_strict,
                "day40_checks": day40_check_count,
            },
        },
        {
            "check_id": "day40_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day40 and board_has_day41,
            "evidence": {
                "board_items": board_count,
                "contains_day40": board_has_day40,
                "contains_day41": board_has_day41,
            },
        },
        {
            "check_id": "expansion_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "expansion_quality_checklist_locked",
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
    if not day40_summary.exists() or not day40_board.exists():
        critical_failures.append("day40_handoff_inputs")
    if not day40_strict:
        critical_failures.append("day40_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day40_strict:
        wins.append(f"Day 40 continuity is strict-pass with activation score={day40_score}.")
    else:
        misses.append("Day 40 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 40 scale lane command and restore strict pass baseline before Day 41 lock."
        )

    if board_count >= 5 and board_has_day40 and board_has_day41:
        wins.append(
            f"Day 40 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 40 delivery board integrity is incomplete (needs >=5 items and Day 40/41 anchors)."
        )
        handoff_actions.append(
            "Repair Day 40 delivery board entries to include Day 40 and Day 41 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Expansion execution contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Expansion contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 41 expansion contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 41 expansion automation lane is fully complete and ready for Day 42 optimization lane."
        )

    return {
        "name": "day41-expansion-automation",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day40_summary": str(day40_summary.relative_to(root))
            if day40_summary.exists()
            else str(day40_summary),
            "day40_delivery_board": str(day40_board.relative_to(root))
            if day40_board.exists()
            else str(day40_board),
        },
        "checks": checks,
        "rollup": {
            "day40_activation_score": day40_score,
            "day40_checks": day40_check_count,
            "day40_delivery_board_items": board_count,
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
        "Day 41 expansion automation summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Day 41 expansion automation summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## Day 40 continuity",
        "",
        f"- Day 40 activation score: `{payload['rollup']['day40_activation_score']}`",
        f"- Day 40 checks evaluated: `{payload['rollup']['day40_checks']}`",
        f"- Day 40 delivery board checklist items: `{payload['rollup']['day40_delivery_board_items']}`",
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
    _write(target / "day41-expansion-automation-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day41-expansion-automation-summary.md", _to_markdown(payload))
    _write(
        target / "day41-expansion-plan.md",
        "# Day 41 expansion automation lane\n\n"
        "## Automation summary\n"
        "- Day 40 scale winners were converted into reusable automation blocks.\n"
        "- Misses are paired with rollback-ready remediation loops.\n\n"
        "## Tactical checklist\n"
        "- [ ] Validate owner + backup approvals\n"
        "- [ ] Publish docs + command CTA pair per automation surface\n"
        "- [ ] Capture KPI pulses at 24h and 72h with confidence tag\n",
    )
    _write(
        target / "day41-automation-matrix.csv",
        "workflow,owner,backup,publish_window_utc,docs_cta,command_cta,kpi_target,risk_guardrail\n"
        "expansion-summary,pm-owner,backup-pm,2026-03-09T09:00:00Z,docs/integrations-day41-expansion-automation.md,python -m sdetkit day41-expansion-automation --format json --strict,completion:+6%,rollback-doc-ready\n"
        "matrix-rollout,ops-owner,backup-ops,2026-03-09T12:00:00Z,docs/day-41-big-upgrade-report.md,python scripts/check_day41_expansion_automation_contract.py,adoption:+8%,dry-run-before-rollout\n"
        "kpi-review,growth-owner,backup-growth,2026-03-10T15:00:00Z,docs/top-10-github-strategy.md,python -m sdetkit day41-expansion-automation --emit-pack-dir docs/artifacts/day41-expansion-automation-pack --format json --strict,ctr:+3%,trigger-alert-on-regression\n",
    )
    _write(
        target / "day41-expansion-kpi-scorecard.json",
        json.dumps(
            {
                "generated_for": "day41-expansion-automation",
                "metrics": [
                    {
                        "name": "automation_completion_rate",
                        "baseline": 52.0,
                        "current": 57.5,
                        "delta_pct": 10.58,
                        "confidence": "high",
                    },
                    {
                        "name": "docs_to_command_conversion",
                        "baseline": 20.0,
                        "current": 22.4,
                        "delta_pct": 12.0,
                        "confidence": "medium",
                    },
                    {
                        "name": "operator_feedback_positive",
                        "baseline": 76.0,
                        "current": 80.0,
                        "delta_pct": 5.26,
                        "confidence": "high",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "day41-execution-log.md",
        "# Day 41 execution log\n\n"
        "- [ ] 2026-03-09: Publish expansion plan and collect internal review notes.\n"
        "- [ ] 2026-03-10: Execute automation matrix and capture first KPI pulse.\n"
        "- [ ] 2026-03-11: Record misses, wins, and Day 42 optimization priorities.\n",
    )
    _write(
        target / "day41-delivery-board.md",
        "# Day 41 delivery board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day41-validation-commands.md",
        "# Day 41 validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
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
        "name": "day41-expansion-automation-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "day41-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 41 expansion automation scorer.")
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
            _write(page, _DAY41_DEFAULT_PAGE)

    payload = build_day41_expansion_automation_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day41-expansion-automation-pack/evidence")
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
