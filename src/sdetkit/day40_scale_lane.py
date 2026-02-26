from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day40-scale-lane.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY39_SUMMARY_PATH = "docs/artifacts/day39-playbook-post-pack/day39-playbook-post-summary.json"
_DAY39_BOARD_PATH = "docs/artifacts/day39-playbook-post-pack/day39-delivery-board.md"
_SECTION_HEADER = "# Day 40 — Scale lane #1"
_REQUIRED_SECTIONS = [
    "## Why Day 40 matters",
    "## Required inputs (Day 39)",
    "## Day 40 command lane",
    "## Scale execution contract",
    "## Scale quality checklist",
    "## Day 40 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day40-scale-lane --format json --strict",
    "python -m sdetkit day40-scale-lane --emit-pack-dir docs/artifacts/day40-scale-lane-pack --format json --strict",
    "python -m sdetkit day40-scale-lane --execute --evidence-dir docs/artifacts/day40-scale-lane-pack/evidence --format json --strict",
    "python scripts/check_day40_scale_lane_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day40-scale-lane --format json --strict",
    "python -m sdetkit day40-scale-lane --emit-pack-dir docs/artifacts/day40-scale-lane-pack --format json --strict",
    "python scripts/check_day40_scale_lane_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 40 scale lane execution and metric follow-up.",
    "The Day 40 scale lane references Day 39 publication winners and explicit misses.",
    "Every Day 40 scale lane section includes docs CTA, runnable command CTA, and one KPI target.",
    "Day 40 closeout records scale learnings and Day 41 expansion priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes executive summary, tactical checklist, and rollout timeline",
    "- [ ] Every section has owner, publish window, and KPI target",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, and delta for each playbook KPI",
    "- [ ] Artifact pack includes scale plan, channel matrix, scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 40 scale plan draft committed",
    "- [ ] Day 40 review notes captured with owner + backup",
    "- [ ] Day 40 rollout timeline exported",
    "- [ ] Day 40 KPI scorecard snapshot exported",
    "- [ ] Day 41 expansion priorities drafted from Day 40 learnings",
]

_DAY40_DEFAULT_PAGE = """# Day 40 — Scale lane #1

Day 40 publishes scale lane #1 that converts Day 39 publication evidence into a reusable operator guide.

## Why Day 40 matters

- Converts Day 39 publication evidence into a reusable post + playbook operating pattern.
- Preserves quality by enforcing owner accountability, CTA integrity, and KPI targets.
- Creates a deterministic handoff from publication outcomes into Day 40 scale priorities.

## Required inputs (Day 39)

- `docs/artifacts/day39-playbook-post-pack/day39-playbook-post-summary.json`
- `docs/artifacts/day39-playbook-post-pack/day39-delivery-board.md`

## Day 40 command lane

```bash
python -m sdetkit day40-scale-lane --format json --strict
python -m sdetkit day40-scale-lane --emit-pack-dir docs/artifacts/day40-scale-lane-pack --format json --strict
python -m sdetkit day40-scale-lane --execute --evidence-dir docs/artifacts/day40-scale-lane-pack/evidence --format json --strict
python scripts/check_day40_scale_lane_contract.py
```

## Scale execution contract

- Single owner + backup reviewer are assigned for Day 40 scale lane execution and metric follow-up.
- The Day 40 scale lane references Day 39 publication winners and explicit misses.
- Every Day 40 scale lane section includes docs CTA, runnable command CTA, and one KPI target.
- Day 40 closeout records scale learnings and Day 41 expansion priorities.

## Scale quality checklist

- [ ] Includes executive summary, tactical checklist, and rollout timeline
- [ ] Every section has owner, publish window, and KPI target
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, and delta for each playbook KPI
- [ ] Artifact pack includes scale plan, channel matrix, scorecard, and execution log

## Day 40 delivery board

- [ ] Day 40 scale plan draft committed
- [ ] Day 40 review notes captured with owner + backup
- [ ] Day 40 rollout timeline exported
- [ ] Day 40 KPI scorecard snapshot exported
- [ ] Day 41 expansion priorities drafted from Day 40 learnings

## Scoring model

Day 40 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 39 continuity and strict baseline carryover: 35 points.
- Publication contract lock + delivery board readiness: 15 points.
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


def _load_day39(path: Path) -> tuple[float, bool, int]:
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
    has_day39 = any("day 39" in line for line in lines)
    has_day40 = any("day 40" in line for line in lines)
    return item_count, has_day39, has_day40


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_day40_scale_lane_summary(
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

    day39_summary = root / _DAY39_SUMMARY_PATH
    day39_board = root / _DAY39_BOARD_PATH
    day39_score, day39_strict, day39_check_count = _load_day39(day39_summary)
    board_count, board_has_day39, board_has_day40 = _board_stats(day39_board)

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
            "check_id": "readme_day40_link",
            "weight": 8,
            "passed": "docs/integrations-day40-scale-lane.md" in readme_text,
            "evidence": "docs/integrations-day40-scale-lane.md",
        },
        {
            "check_id": "readme_day40_command",
            "weight": 4,
            "passed": "day40-scale-lane" in readme_text,
            "evidence": "day40-scale-lane",
        },
        {
            "check_id": "docs_index_day40_links",
            "weight": 8,
            "passed": (
                "day-40-big-upgrade-report.md" in docs_index_text
                and "integrations-day40-scale-lane.md" in docs_index_text
            ),
            "evidence": "day-40-big-upgrade-report.md + integrations-day40-scale-lane.md",
        },
        {
            "check_id": "top10_day40_alignment",
            "weight": 5,
            "passed": ("Day 40" in top10_text and "Day 41" in top10_text),
            "evidence": "Day 40 + Day 41 strategy chain",
        },
        {
            "check_id": "day39_summary_present",
            "weight": 10,
            "passed": day39_summary.exists(),
            "evidence": str(day39_summary),
        },
        {
            "check_id": "day39_delivery_board_present",
            "weight": 8,
            "passed": day39_board.exists(),
            "evidence": str(day39_board),
        },
        {
            "check_id": "day39_quality_floor",
            "weight": 10,
            "passed": day39_strict and day39_score >= 95,
            "evidence": {
                "day39_score": day39_score,
                "strict_pass": day39_strict,
                "day39_checks": day39_check_count,
            },
        },
        {
            "check_id": "day39_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day39 and board_has_day40,
            "evidence": {
                "board_items": board_count,
                "contains_day39": board_has_day39,
                "contains_day40": board_has_day40,
            },
        },
        {
            "check_id": "playbook_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "playbook_quality_checklist_locked",
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
    if not day39_summary.exists() or not day39_board.exists():
        critical_failures.append("day39_handoff_inputs")
    if not day39_strict:
        critical_failures.append("day39_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day39_strict:
        wins.append(f"Day 39 continuity is strict-pass with activation score={day39_score}.")
    else:
        misses.append("Day 39 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 39 scale lane command and restore strict pass baseline before Day 40 lock."
        )

    if board_count >= 5 and board_has_day39 and board_has_day40:
        wins.append(
            f"Day 39 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 39 delivery board integrity is incomplete (needs >=5 items and Day 39/40 anchors)."
        )
        handoff_actions.append(
            "Repair Day 39 delivery board entries to include Day 39 and Day 40 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Scale execution contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Playbook contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 40 scale contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append("Day 40 scale lane #1 is fully complete and ready for Day 41 expansion lane.")

    return {
        "name": "day40-scale-lane",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day39_summary": str(day39_summary.relative_to(root))
            if day39_summary.exists()
            else str(day39_summary),
            "day39_delivery_board": str(day39_board.relative_to(root))
            if day39_board.exists()
            else str(day39_board),
        },
        "checks": checks,
        "rollup": {
            "day39_activation_score": day39_score,
            "day39_checks": day39_check_count,
            "day39_delivery_board_items": board_count,
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
        "Day 40 scale lane summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Day 40 scale lane summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## Day 39 continuity",
        "",
        f"- Day 39 activation score: `{payload['rollup']['day39_activation_score']}`",
        f"- Day 39 checks evaluated: `{payload['rollup']['day39_checks']}`",
        f"- Day 39 delivery board checklist items: `{payload['rollup']['day39_delivery_board_items']}`",
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
    _write(target / "day40-scale-lane-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day40-scale-lane-summary.md", _to_markdown(payload))
    _write(
        target / "day40-scale-plan.md",
        "# Day 40 scale lane #1\n\n"
        "## Executive summary\n"
        "- Day 39 winners were converted into a repeatable publishing pattern.\n"
        "- Misses were mapped to actionable guardrails for next wave execution.\n\n"
        "## Tactical checklist\n"
        "- [ ] Validate owner + backup approvals\n"
        "- [ ] Publish docs + command CTA pair for each section\n"
        "- [ ] Capture KPI pulse after 24h and 72h\n",
    )
    _write(
        target / "day40-channel-matrix.csv",
        "section,owner,backup,publish_window_utc,docs_cta,command_cta,kpi_target\n"
        "executive-summary,pm-owner,backup-pm,2026-03-06T09:00:00Z,docs/integrations-day40-scale-lane.md,python -m sdetkit day40-scale-lane --format json --strict,completion:+5%\n"
        "tactical-checklist,ops-owner,backup-ops,2026-03-06T12:00:00Z,docs/day-40-big-upgrade-report.md,python scripts/check_day40_scale_lane_contract.py,adoption:+7%\n"
        "rollout-timeline,growth-owner,backup-growth,2026-03-07T15:00:00Z,docs/top-10-github-strategy.md,python -m sdetkit day40-scale-lane --emit-pack-dir docs/artifacts/day40-scale-lane-pack --format json --strict,ctr:+2%\n",
    )
    _write(
        target / "day40-scale-kpi-scorecard.json",
        json.dumps(
            {
                "generated_for": "day40-scale-lane",
                "metrics": [
                    {
                        "name": "playbook_read_completion",
                        "baseline": 41.2,
                        "current": 44.4,
                        "delta_pct": 7.77,
                    },
                    {
                        "name": "docs_to_command_adoption",
                        "baseline": 18.6,
                        "current": 20.0,
                        "delta_pct": 7.53,
                    },
                    {
                        "name": "operator_feedback_positive",
                        "baseline": 72.0,
                        "current": 76.0,
                        "delta_pct": 5.56,
                    },
                ],
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "day40-execution-log.md",
        "# Day 40 execution log\n\n"
        "- [ ] 2026-03-06: Publish playbook draft and collect internal review notes.\n"
        "- [ ] 2026-03-07: Execute rollout timeline and capture first KPI pulse.\n"
        "- [ ] 2026-03-08: Record misses, wins, and Day 40 scale priorities.\n",
    )
    _write(
        target / "day40-delivery-board.md",
        "# Day 40 delivery board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day40-validation-commands.md",
        "# Day 40 validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
    )


def _run_execution(root: Path, evidence_dir: Path) -> None:
    target = (root / evidence_dir).resolve() if not evidence_dir.is_absolute() else evidence_dir
    target.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    for command in _EXECUTION_COMMANDS:
        proc = subprocess.run(
            shlex.split(command), cwd=root, text=True, capture_output=True, check=False
        )
        logs.append(
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
    summary = {
        "name": "day40-scale-lane-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "day40-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 40 scale lane scorer.")
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
            _write(page, _DAY40_DEFAULT_PAGE)

    payload = build_day40_scale_lane_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day40-scale-lane-pack/evidence")
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
