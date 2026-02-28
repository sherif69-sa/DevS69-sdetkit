from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day52-narrative-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY51_SUMMARY_PATH = (
    "docs/artifacts/day51-case-snippet-closeout-pack/day51-case-snippet-closeout-summary.json"
)
_DAY51_BOARD_PATH = "docs/artifacts/day51-case-snippet-closeout-pack/day51-delivery-board.md"
_SECTION_HEADER = "# Day 52 \u2014 Narrative closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 52 matters",
    "## Required inputs (Day 51)",
    "## Day 52 command lane",
    "## Narrative closeout contract",
    "## Narrative quality checklist",
    "## Day 52 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day52-narrative-closeout --format json --strict",
    "python -m sdetkit day52-narrative-closeout --emit-pack-dir docs/artifacts/day52-narrative-closeout-pack --format json --strict",
    "python -m sdetkit day52-narrative-closeout --execute --evidence-dir docs/artifacts/day52-narrative-closeout-pack/evidence --format json --strict",
    "python scripts/check_day52_narrative_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day52-narrative-closeout --format json --strict",
    "python -m sdetkit day52-narrative-closeout --emit-pack-dir docs/artifacts/day52-narrative-closeout-pack --format json --strict",
    "python scripts/check_day52_narrative_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 52 narrative execution and KPI follow-up.",
    "The Day 52 narrative lane references Day 51 case-snippet winners and misses with deterministic release-storytelling loops.",
    "Every Day 52 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.",
    "Day 52 closeout records narrative learnings and Day 53 expansion priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes wins/misses digest, proof snippet draft, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes narrative brief, proof map, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 52 narrative brief committed",
    "- [ ] Day 52 narrative reviewed with owner + backup",
    "- [ ] Day 52 proof map exported",
    "- [ ] Day 52 KPI scorecard snapshot exported",
    "- [ ] Day 53 expansion priorities drafted from Day 52 learnings",
]

_DAY52_DEFAULT_PAGE = """# Day 52 \u2014 Narrative closeout lane

Day 52 closes with a major narrative upgrade that converts Day 51 case-snippet evidence into a deterministic release-storytelling lane.

## Why Day 52 matters

- Converts Day 51 case-snippet proof into release-storytelling discipline.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from Day 52 narratives into Day 52 narrative execution.

## Required inputs (Day 51)

- `docs/artifacts/day51-case-snippet-closeout-pack/day51-case-snippet-closeout-summary.json`
- `docs/artifacts/day51-case-snippet-closeout-pack/day51-delivery-board.md`

## Day 52 command lane

```bash
python -m sdetkit day52-narrative-closeout --format json --strict
python -m sdetkit day52-narrative-closeout --emit-pack-dir docs/artifacts/day52-narrative-closeout-pack --format json --strict
python -m sdetkit day52-narrative-closeout --execute --evidence-dir docs/artifacts/day52-narrative-closeout-pack/evidence --format json --strict
python scripts/check_day52_narrative_closeout_contract.py
```

## Narrative closeout contract

- Single owner + backup reviewer are assigned for Day 52 narrative execution and KPI follow-up.
- The Day 52 narrative lane references Day 51 case-snippet winners and misses with deterministic release-storytelling loops.
- Every Day 52 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Day 52 closeout records narrative learnings and Day 53 expansion priorities.

## Narrative quality checklist

- [ ] Includes wins/misses digest, proof snippet draft, and rollback strategy
- [ ] Every section has owner, review window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes narrative brief, proof map, KPI scorecard, and execution log

## Day 52 delivery board

- [ ] Day 52 narrative brief committed
- [ ] Day 52 narrative reviewed with owner + backup
- [ ] Day 52 proof map exported
- [ ] Day 52 KPI scorecard snapshot exported
- [ ] Day 53 expansion priorities drafted from Day 52 learnings

## Scoring model

Day 52 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 51 continuity and strict baseline carryover: 35 points.
- Narrative contract lock + delivery board readiness: 15 points.
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


def _load_day51(path: Path) -> tuple[float, bool, int]:
    data_obj = _load_json(path)
    if not isinstance(data_obj, dict):
        return 0.0, False, 0
    summary_obj = data_obj.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    checks_obj = data_obj.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    score = float(summary.get("activation_score", 0.0))
    strict = bool(summary.get("strict_pass", False))
    check_count = len(checks)
    return score, strict, check_count


def _contains_all_lines(text: str, required_lines: list[str]) -> list[str]:
    return [line for line in required_lines if line not in text]


def _board_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- [")]
    return len(lines), ("Day 51" in text), ("Day 52" in text)


def build_day52_narrative_closeout_summary(root: Path) -> dict[str, Any]:
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

    day51_summary = root / _DAY51_SUMMARY_PATH
    day51_board = root / _DAY51_BOARD_PATH
    day51_score, day51_strict, day51_check_count = _load_day51(day51_summary)
    board_count, board_has_day51, board_has_day52 = _board_stats(day51_board)

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
            "check_id": "readme_day52_link",
            "weight": 8,
            "passed": "docs/integrations-day52-narrative-closeout.md" in readme_text,
            "evidence": "docs/integrations-day52-narrative-closeout.md",
        },
        {
            "check_id": "readme_day52_command",
            "weight": 4,
            "passed": "day52-narrative-closeout" in readme_text,
            "evidence": "day52-narrative-closeout",
        },
        {
            "check_id": "docs_index_day52_links",
            "weight": 8,
            "passed": (
                "day-52-big-upgrade-report.md" in docs_index_text
                and "integrations-day52-narrative-closeout.md" in docs_index_text
            ),
            "evidence": "day-52-big-upgrade-report.md + integrations-day52-narrative-closeout.md",
        },
        {
            "check_id": "top10_day52_alignment",
            "weight": 5,
            "passed": ("Day 52" in top10_text and "Day 53" in top10_text),
            "evidence": "Day 52 + Day 53 strategy chain",
        },
        {
            "check_id": "day51_summary_present",
            "weight": 10,
            "passed": day51_summary.exists(),
            "evidence": str(day51_summary),
        },
        {
            "check_id": "day51_delivery_board_present",
            "weight": 8,
            "passed": day51_board.exists(),
            "evidence": str(day51_board),
        },
        {
            "check_id": "day51_quality_floor",
            "weight": 10,
            "passed": day51_strict and day51_score >= 95,
            "evidence": {
                "day51_score": day51_score,
                "strict_pass": day51_strict,
                "day51_checks": day51_check_count,
            },
        },
        {
            "check_id": "day51_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day51 and board_has_day52,
            "evidence": {
                "board_items": board_count,
                "contains_day51": board_has_day51,
                "contains_day52": board_has_day52,
            },
        },
        {
            "check_id": "narrative_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "narrative_quality_checklist_locked",
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
    score = int(round(sum(c["weight"] for c in checks if bool(c["passed"]))))
    critical_failures: list[str] = []
    if not day51_summary.exists() or not day51_board.exists():
        critical_failures.append("day51_handoff_inputs")
    if not day51_strict:
        critical_failures.append("day51_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day51_strict:
        wins.append(f"Day 51 continuity is strict-pass with activation score={day51_score}.")
    else:
        misses.append("Day 51 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 51 case snippet closeout command and restore strict pass baseline before Day 52 lock."
        )

    if board_count >= 5 and board_has_day51 and board_has_day52:
        wins.append(
            f"Day 51 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 51 delivery board integrity is incomplete (needs >=5 items and Day 51/52 anchors)."
        )
        handoff_actions.append(
            "Repair Day 51 delivery board entries to include Day 51 and Day 52 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Narrative contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Narrative contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 52 narrative contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 52 narrative closeout lane is fully complete and ready for Day 53 execution lane."
        )

    return {
        "name": "day52-narrative-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day51_summary": str(day51_summary.relative_to(root))
            if day51_summary.exists()
            else str(day51_summary),
            "day51_delivery_board": str(day51_board.relative_to(root))
            if day51_board.exists()
            else str(day51_board),
        },
        "checks": checks,
        "rollup": {
            "day51_activation_score": day51_score,
            "day51_checks": day51_check_count,
            "day51_delivery_board_items": board_count,
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
        "Day 52 narrative closeout summary",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- Day 51 activation score: `{payload['rollup']['day51_activation_score']}`",
        f"- Day 51 checks evaluated: `{payload['rollup']['day51_checks']}`",
        f"- Day 51 delivery board checklist items: `{payload['rollup']['day51_delivery_board_items']}`",
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
    _write(target / "day52-narrative-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day52-narrative-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "day52-narrative-brief.md",
        "# Day 52 Narrative Brief\n\n- Objective: close Day 52 with measurable release-storytelling discipline and proof-backed narrative gains.\n",
    )
    _write(
        target / "day52-proof-map.csv",
        "stream,owner,backup,review_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "narrative-floor,qa-lead,docs-owner,2026-03-19T10:00:00Z,docs/integrations-day52-narrative-closeout.md,python -m sdetkit day52-narrative-closeout --format json --strict,failed-checks:0,narrative-drift\n",
    )
    _write(
        target / "day52-narrative-kpi-scorecard.json",
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
        target / "day52-execution-log.md",
        "# Day 52 Execution Log\n\n- [ ] 2026-03-19: Record misses, wins, and Day 53 expansion priorities.\n",
    )
    _write(
        target / "day52-delivery-board.md",
        "# Day 52 Delivery Board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day52-validation-commands.md",
        "# Day 52 Validation Commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        evidence_path / "day52-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 52 narrative closeout checks")
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
            _write(page, _DAY52_DEFAULT_PAGE)

    payload = build_day52_narrative_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day52-narrative-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
