from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day49-weekly-review-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY48_SUMMARY_PATH = (
    "docs/artifacts/day48-objection-closeout-pack/day48-objection-closeout-summary.json"
)
_DAY48_BOARD_PATH = "docs/artifacts/day48-objection-closeout-pack/day48-delivery-board.md"
_SECTION_HEADER = "# Day 49 \u2014 Weekly review closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 49 matters",
    "## Required inputs (Day 48)",
    "## Day 49 command lane",
    "## Weekly review closeout contract",
    "## Weekly review quality checklist",
    "## Day 49 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day49-weekly-review-closeout --format json --strict",
    "python -m sdetkit day49-weekly-review-closeout --emit-pack-dir docs/artifacts/day49-weekly-review-closeout-pack --format json --strict",
    "python -m sdetkit day49-weekly-review-closeout --execute --evidence-dir docs/artifacts/day49-weekly-review-closeout-pack/evidence --format json --strict",
    "python scripts/check_day49_weekly_review_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day49-weekly-review-closeout --format json --strict",
    "python -m sdetkit day49-weekly-review-closeout --emit-pack-dir docs/artifacts/day49-weekly-review-closeout-pack --format json --strict",
    "python scripts/check_day49_weekly_review_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 49 weekly review execution and KPI follow-up.",
    "The Day 49 weekly review lane references Day 48 objection winners and misses with deterministic prioritization loops.",
    "Every Day 49 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.",
    "Day 49 closeout records weekly-review learnings and Day 50 execution priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes wins/misses digest, risk register, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes review brief, risk map, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 49 weekly review brief committed",
    "- [ ] Day 49 priorities reviewed with owner + backup",
    "- [ ] Day 49 risk register exported",
    "- [ ] Day 49 KPI scorecard snapshot exported",
    "- [ ] Day 50 execution priorities drafted from Day 49 learnings",
]

_DAY49_DEFAULT_PAGE = """# Day 49 \u2014 Weekly review closeout lane

Day 49 closes with a major weekly-review upgrade that converts Day 48 objection evidence into deterministic prioritization and handoff loops.

## Why Day 49 matters

- Converts Day 48 objection proof into weekly review execution discipline.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from weekly-review outcomes into Day 50 execution priorities.

## Required inputs (Day 48)

- `docs/artifacts/day48-objection-closeout-pack/day48-objection-closeout-summary.json`
- `docs/artifacts/day48-objection-closeout-pack/day48-delivery-board.md`

## Day 49 command lane

```bash
python -m sdetkit day49-weekly-review-closeout --format json --strict
python -m sdetkit day49-weekly-review-closeout --emit-pack-dir docs/artifacts/day49-weekly-review-closeout-pack --format json --strict
python -m sdetkit day49-weekly-review-closeout --execute --evidence-dir docs/artifacts/day49-weekly-review-closeout-pack/evidence --format json --strict
python scripts/check_day49_weekly_review_closeout_contract.py
```

## Weekly review closeout contract

- Single owner + backup reviewer are assigned for Day 49 weekly review execution and KPI follow-up.
- The Day 49 weekly review lane references Day 48 objection winners and misses with deterministic prioritization loops.
- Every Day 49 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Day 49 closeout records weekly-review learnings and Day 50 execution priorities.

## Weekly review quality checklist

- [ ] Includes wins/misses digest, risk register, and rollback strategy
- [ ] Every section has owner, review window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes review brief, risk map, KPI scorecard, and execution log

## Day 49 delivery board

- [ ] Day 49 weekly review brief committed
- [ ] Day 49 priorities reviewed with owner + backup
- [ ] Day 49 risk register exported
- [ ] Day 49 KPI scorecard snapshot exported
- [ ] Day 50 execution priorities drafted from Day 49 learnings

## Scoring model

Day 49 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 48 continuity and strict baseline carryover: 35 points.
- Weekly review contract lock + delivery board readiness: 15 points.
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


def _load_day48(path: Path) -> tuple[float, bool, int]:
    data = _load_json(path)
    if data is None:
        return 0.0, False, 0
    summary = data.get("summary")
    checks = data.get("checks")
    score = summary.get("activation_score") if isinstance(summary, dict) else None
    strict_pass = summary.get("strict_pass") if isinstance(summary, dict) else False
    count = len(checks) if isinstance(checks, list) else 0
    return float(score or 0.0), bool(strict_pass), count


def _board_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    items = [line for line in text.splitlines() if line.strip().startswith("- [")]
    return len(items), "Day 48" in text, "Day 49" in text


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_day49_weekly_review_closeout_summary(root: Path) -> dict[str, Any]:
    readme_path = "README.md"
    docs_index_path = "docs/index.md"
    docs_page_path = _PAGE_PATH
    top10_path = _TOP10_PATH

    readme_text = _read(root / readme_path)
    docs_index_text = _read(root / docs_index_path)
    page_path = root / docs_page_path
    page_text = _read(page_path)
    top10_text = _read(root / top10_path)

    missing_sections = [s for s in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if s not in page_text]
    missing_commands = [c for c in _REQUIRED_COMMANDS if c not in page_text]
    missing_contract_lines = _contains_all_lines(
        page_text, [f"- {line}" for line in _REQUIRED_CONTRACT_LINES]
    )
    missing_quality_lines = _contains_all_lines(page_text, _REQUIRED_QUALITY_LINES)
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    day48_summary = root / _DAY48_SUMMARY_PATH
    day48_board = root / _DAY48_BOARD_PATH
    day48_score, day48_strict, day48_check_count = _load_day48(day48_summary)
    board_count, board_has_day48, board_has_day49 = _board_stats(day48_board)

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
            "check_id": "readme_day49_link",
            "weight": 8,
            "passed": "docs/integrations-day49-weekly-review-closeout.md" in readme_text,
            "evidence": "docs/integrations-day49-weekly-review-closeout.md",
        },
        {
            "check_id": "readme_day49_command",
            "weight": 4,
            "passed": "day49-weekly-review-closeout" in readme_text,
            "evidence": "day49-weekly-review-closeout",
        },
        {
            "check_id": "docs_index_day49_links",
            "weight": 8,
            "passed": (
                "day-49-big-upgrade-report.md" in docs_index_text
                and "integrations-day49-weekly-review-closeout.md" in docs_index_text
            ),
            "evidence": "day-49-big-upgrade-report.md + integrations-day49-weekly-review-closeout.md",
        },
        {
            "check_id": "top10_day49_alignment",
            "weight": 5,
            "passed": ("Day 49" in top10_text and "Day 50" in top10_text),
            "evidence": "Day 49 + Day 50 strategy chain",
        },
        {
            "check_id": "day48_summary_present",
            "weight": 10,
            "passed": day48_summary.exists(),
            "evidence": str(day48_summary),
        },
        {
            "check_id": "day48_delivery_board_present",
            "weight": 8,
            "passed": day48_board.exists(),
            "evidence": str(day48_board),
        },
        {
            "check_id": "day48_quality_floor",
            "weight": 10,
            "passed": day48_strict and day48_score >= 95,
            "evidence": {
                "day48_score": day48_score,
                "strict_pass": day48_strict,
                "day48_checks": day48_check_count,
            },
        },
        {
            "check_id": "day48_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day48 and board_has_day49,
            "evidence": {
                "board_items": board_count,
                "contains_day48": board_has_day48,
                "contains_day49": board_has_day49,
            },
        },
        {
            "check_id": "weekly_review_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "weekly_review_quality_checklist_locked",
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
    if not day48_summary.exists() or not day48_board.exists():
        critical_failures.append("day48_handoff_inputs")
    if not day48_strict:
        critical_failures.append("day48_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day48_strict:
        wins.append(f"Day 48 continuity is strict-pass with activation score={day48_score}.")
    else:
        misses.append("Day 48 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 48 objection closeout command and restore strict pass baseline before Day 49 lock."
        )

    if board_count >= 5 and board_has_day48 and board_has_day49:
        wins.append(
            f"Day 48 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 48 delivery board integrity is incomplete (needs >=5 items and Day 48/49 anchors)."
        )
        handoff_actions.append(
            "Repair Day 48 delivery board entries to include Day 48 and Day 49 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Weekly review execution contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Weekly review contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 49 weekly review contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 49 weekly review closeout lane is fully complete and ready for Day 50 execution lane."
        )

    return {
        "name": "day49-weekly-review-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day48_summary": str(day48_summary.relative_to(root))
            if day48_summary.exists()
            else str(day48_summary),
            "day48_delivery_board": str(day48_board.relative_to(root))
            if day48_board.exists()
            else str(day48_board),
        },
        "checks": checks,
        "rollup": {
            "day48_activation_score": day48_score,
            "day48_checks": day48_check_count,
            "day48_delivery_board_items": board_count,
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


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Day 49 weekly review closeout summary",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- Day 48 activation score: `{payload['rollup']['day48_activation_score']}`",
        f"- Day 48 checks evaluated: `{payload['rollup']['day48_checks']}`",
        f"- Day 48 delivery board checklist items: `{payload['rollup']['day48_delivery_board_items']}`",
    ]
    if payload["wins"]:
        lines.append("- Wins:")
        lines.extend([f"  - {w}" for w in payload["wins"]])
    if payload["misses"]:
        lines.append("- Misses:")
        lines.extend([f"  - {m}" for m in payload["misses"]])
    return "\n".join(lines)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _emit_pack(root: Path, payload: dict[str, Any], pack_dir: Path) -> None:
    target = root / pack_dir
    target.mkdir(parents=True, exist_ok=True)
    _write(
        target / "day49-weekly-review-closeout-summary.json", json.dumps(payload, indent=2) + "\n"
    )
    _write(target / "day49-weekly-review-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "day49-weekly-review-brief.md",
        "# Day 49 Weekly Review Brief\n\n- Objective: close Day 49 with measurable weekly-review discipline and prioritized execution gains.\n",
    )
    _write(
        target / "day49-weekly-review-risk-register.csv",
        "stream,owner,backup,review_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "weekly-review-floor,qa-lead,docs-owner,2026-03-17T10:00:00Z,docs/integrations-day49-weekly-review-closeout.md,python -m sdetkit day49-weekly-review-closeout --format json --strict,failed-checks:0,priority-drift\n",
    )
    _write(
        target / "day49-weekly-review-kpi-scorecard.json",
        json.dumps(
            {
                "kpis": [
                    {
                        "id": "strict_pass",
                        "baseline": 1,
                        "current": int(payload["summary"]["strict_pass"]),
                        "delta": int(payload["summary"]["strict_pass"]) - 1,
                        "confidence": "high",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "day49-execution-log.md",
        "# Day 49 Execution Log\n\n- [ ] 2026-03-17: Record misses, wins, and Day 50 execution priorities.\n",
    )
    _write(
        target / "day49-delivery-board.md",
        "# Day 49 Delivery Board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day49-validation-commands.md",
        "# Day 49 Validation Commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    evidence_path = root / evidence_dir
    evidence_path.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = []
    for index, command in enumerate(_EXECUTION_COMMANDS, start=1):
        argv = shlex.split(command)
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        proc = subprocess.run(argv, cwd=root, text=True, capture_output=True, check=False)
        event = {
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        events.append(event)
        _write(evidence_path / f"command-{index:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        evidence_path / "day49-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 49 weekly review closeout checks")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--ensure-doc", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.ensure_doc:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DAY49_DEFAULT_PAGE)

    payload = build_day49_weekly_review_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day49-weekly-review-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
