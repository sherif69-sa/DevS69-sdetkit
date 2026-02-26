from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day50-execution-prioritization-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY49_SUMMARY_PATH = (
    "docs/artifacts/day49-weekly-review-closeout-pack/day49-weekly-review-closeout-summary.json"
)
_DAY49_BOARD_PATH = "docs/artifacts/day49-weekly-review-closeout-pack/day49-delivery-board.md"
_SECTION_HEADER = "# Day 50 — Execution prioritization closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 50 matters",
    "## Required inputs (Day 49)",
    "## Day 50 command lane",
    "## Execution prioritization closeout contract",
    "## Execution prioritization quality checklist",
    "## Day 50 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day50-execution-prioritization-closeout --format json --strict",
    "python -m sdetkit day50-execution-prioritization-closeout --emit-pack-dir docs/artifacts/day50-execution-prioritization-closeout-pack --format json --strict",
    "python -m sdetkit day50-execution-prioritization-closeout --execute --evidence-dir docs/artifacts/day50-execution-prioritization-closeout-pack/evidence --format json --strict",
    "python scripts/check_day50_execution_prioritization_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day50-execution-prioritization-closeout --format json --strict",
    "python -m sdetkit day50-execution-prioritization-closeout --emit-pack-dir docs/artifacts/day50-execution-prioritization-closeout-pack --format json --strict",
    "python scripts/check_day50_execution_prioritization_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 50 execution prioritization execution and KPI follow-up.",
    "The Day 50 execution prioritization lane references Day 49 weekly-review winners and misses with deterministic execution-board loops.",
    "Every Day 50 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.",
    "Day 50 closeout records execution-board learnings and Day 51 release priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes wins/misses digest, risk register, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes execution brief, risk map, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 50 execution prioritization brief committed",
    "- [ ] Day 50 priorities reviewed with owner + backup",
    "- [ ] Day 50 risk register exported",
    "- [ ] Day 50 KPI scorecard snapshot exported",
    "- [ ] Day 51 release priorities drafted from Day 50 learnings",
]

_DAY50_DEFAULT_PAGE = """# Day 50 — Execution prioritization closeout lane

Day 50 closes with a major execution-prioritization upgrade that converts Day 49 weekly-review evidence into a deterministic execution board and release-storytelling handoff.

## Why Day 50 matters

- Converts Day 49 weekly-review proof into execution-board discipline.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from execution priorities into Day 51 storytelling priorities.

## Required inputs (Day 49)

- `docs/artifacts/day49-weekly-review-closeout-pack/day49-weekly-review-closeout-summary.json`
- `docs/artifacts/day49-weekly-review-closeout-pack/day49-delivery-board.md`

## Day 50 command lane

```bash
python -m sdetkit day50-execution-prioritization-closeout --format json --strict
python -m sdetkit day50-execution-prioritization-closeout --emit-pack-dir docs/artifacts/day50-execution-prioritization-closeout-pack --format json --strict
python -m sdetkit day50-execution-prioritization-closeout --execute --evidence-dir docs/artifacts/day50-execution-prioritization-closeout-pack/evidence --format json --strict
python scripts/check_day50_execution_prioritization_closeout_contract.py
```

## Execution prioritization closeout contract

- Single owner + backup reviewer are assigned for Day 50 execution prioritization execution and KPI follow-up.
- The Day 50 execution prioritization lane references Day 49 weekly-review winners and misses with deterministic execution-board loops.
- Every Day 50 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Day 50 closeout records execution-board learnings and Day 51 release priorities.

## Execution prioritization quality checklist

- [ ] Includes wins/misses digest, risk register, and rollback strategy
- [ ] Every section has owner, review window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes execution brief, risk map, KPI scorecard, and execution log

## Day 50 delivery board

- [ ] Day 50 execution prioritization brief committed
- [ ] Day 50 priorities reviewed with owner + backup
- [ ] Day 50 risk register exported
- [ ] Day 50 KPI scorecard snapshot exported
- [ ] Day 51 release priorities drafted from Day 50 learnings

## Scoring model

Day 50 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 49 continuity and strict baseline carryover: 35 points.
- Execution prioritization contract lock + delivery board readiness: 15 points.
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


def _load_day49(path: Path) -> tuple[float, bool, int]:
    data = _load_json(path)
    if data is None:
        return 0.0, False, 0
    summary = data.get("summary")
    checks = data.get("checks")
    if not isinstance(summary, dict):
        return 0.0, False, 0
    score = float(summary.get("activation_score", 0.0))
    strict = bool(summary.get("strict_pass", False))
    check_count = len(checks) if isinstance(checks, list) else 0
    return score, strict, check_count


def _contains_all_lines(text: str, required_lines: list[str]) -> list[str]:
    return [line for line in required_lines if line not in text]


def _board_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- [")]
    return len(lines), ("Day 49" in text), ("Day 50" in text)


def build_day50_execution_prioritization_closeout_summary(root: Path) -> dict[str, Any]:
    readme_path = "README.md"
    docs_index_path = "docs/index.md"
    docs_page_path = _PAGE_PATH
    top10_path = _TOP10_PATH

    readme_text = _read(root / readme_path)
    docs_index_text = _read(root / docs_index_path)
    page_path = root / docs_page_path
    page_text = _read(page_path)
    top10_text = _read(root / top10_path)

    missing_sections = [
        item for item in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if item not in page_text
    ]
    missing_commands = _contains_all_lines(page_text, _REQUIRED_COMMANDS)
    missing_contract_lines = _contains_all_lines(
        page_text, [f"- {line}" for line in _REQUIRED_CONTRACT_LINES]
    )
    missing_quality_lines = _contains_all_lines(page_text, _REQUIRED_QUALITY_LINES)
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    day49_summary = root / _DAY49_SUMMARY_PATH
    day49_board = root / _DAY49_BOARD_PATH
    day49_score, day49_strict, day49_check_count = _load_day49(day49_summary)
    board_count, board_has_day49, board_has_day50 = _board_stats(day49_board)

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
            "check_id": "readme_day50_link",
            "weight": 8,
            "passed": "docs/integrations-day50-execution-prioritization-closeout.md" in readme_text,
            "evidence": "docs/integrations-day50-execution-prioritization-closeout.md",
        },
        {
            "check_id": "readme_day50_command",
            "weight": 4,
            "passed": "day50-execution-prioritization-closeout" in readme_text,
            "evidence": "day50-execution-prioritization-closeout",
        },
        {
            "check_id": "docs_index_day50_links",
            "weight": 8,
            "passed": (
                "day-50-big-upgrade-report.md" in docs_index_text
                and "integrations-day50-execution-prioritization-closeout.md" in docs_index_text
            ),
            "evidence": "day-50-big-upgrade-report.md + integrations-day50-execution-prioritization-closeout.md",
        },
        {
            "check_id": "top10_day50_alignment",
            "weight": 5,
            "passed": ("Day 50" in top10_text and "Day 51" in top10_text),
            "evidence": "Day 50 + Day 51 strategy chain",
        },
        {
            "check_id": "day49_summary_present",
            "weight": 10,
            "passed": day49_summary.exists(),
            "evidence": str(day49_summary),
        },
        {
            "check_id": "day49_delivery_board_present",
            "weight": 8,
            "passed": day49_board.exists(),
            "evidence": str(day49_board),
        },
        {
            "check_id": "day49_quality_floor",
            "weight": 10,
            "passed": day49_strict and day49_score >= 95,
            "evidence": {
                "day49_score": day49_score,
                "strict_pass": day49_strict,
                "day49_checks": day49_check_count,
            },
        },
        {
            "check_id": "day49_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day49 and board_has_day50,
            "evidence": {
                "board_items": board_count,
                "contains_day49": board_has_day49,
                "contains_day50": board_has_day50,
            },
        },
        {
            "check_id": "execution_prioritization_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "execution_prioritization_quality_checklist_locked",
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
    if not day49_summary.exists() or not day49_board.exists():
        critical_failures.append("day49_handoff_inputs")
    if not day49_strict:
        critical_failures.append("day49_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day49_strict:
        wins.append(f"Day 49 continuity is strict-pass with activation score={day49_score}.")
    else:
        misses.append("Day 49 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 49 weekly review closeout command and restore strict pass baseline before Day 50 lock."
        )

    if board_count >= 5 and board_has_day49 and board_has_day50:
        wins.append(
            f"Day 49 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 49 delivery board integrity is incomplete (needs >=5 items and Day 49/50 anchors)."
        )
        handoff_actions.append(
            "Repair Day 49 delivery board entries to include Day 49 and Day 50 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Execution prioritization contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Execution prioritization contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 50 execution prioritization contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 50 execution prioritization closeout lane is fully complete and ready for Day 51 execution lane."
        )

    return {
        "name": "day50-execution-prioritization-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day49_summary": str(day49_summary.relative_to(root))
            if day49_summary.exists()
            else str(day49_summary),
            "day49_delivery_board": str(day49_board.relative_to(root))
            if day49_board.exists()
            else str(day49_board),
        },
        "checks": checks,
        "rollup": {
            "day49_activation_score": day49_score,
            "day49_checks": day49_check_count,
            "day49_delivery_board_items": board_count,
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
        "Day 50 execution prioritization closeout summary",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- Day 49 activation score: `{payload['rollup']['day49_activation_score']}`",
        f"- Day 49 checks evaluated: `{payload['rollup']['day49_checks']}`",
        f"- Day 49 delivery board checklist items: `{payload['rollup']['day49_delivery_board_items']}`",
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
        target / "day50-execution-prioritization-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(
        target / "day50-execution-prioritization-closeout-summary.md", _render_text(payload) + "\n"
    )
    _write(
        target / "day50-execution-prioritization-brief.md",
        "# Day 50 Execution Prioritization Brief\n\n- Objective: close Day 50 with measurable execution-board discipline and prioritized release storytelling gains.\n",
    )
    _write(
        target / "day50-risk-register.csv",
        "stream,owner,backup,review_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "execution-prioritization-floor,qa-lead,docs-owner,2026-03-18T10:00:00Z,docs/integrations-day50-execution-prioritization-closeout.md,python -m sdetkit day50-execution-prioritization-closeout --format json --strict,failed-checks:0,priority-drift\n",
    )
    _write(
        target / "day50-execution-prioritization-kpi-scorecard.json",
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
        target / "day50-execution-log.md",
        "# Day 50 Execution Log\n\n- [ ] 2026-03-18: Record misses, wins, and Day 51 release priorities.\n",
    )
    _write(
        target / "day50-delivery-board.md",
        "# Day 50 Delivery Board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day50-validation-commands.md",
        "# Day 50 Validation Commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    evidence_path = root / evidence_dir
    evidence_path.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = []
    for index, command in enumerate(_EXECUTION_COMMANDS, start=1):
        proc = subprocess.run(
            shlex.split(command), cwd=root, text=True, capture_output=True, check=False
        )
        event = {
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        events.append(event)
        _write(evidence_path / f"command-{index:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        evidence_path / "day50-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 50 execution prioritization closeout checks")
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
            _write(page, _DAY50_DEFAULT_PAGE)

    payload = build_day50_execution_prioritization_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day50-execution-prioritization-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
