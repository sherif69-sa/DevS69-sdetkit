from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day71-case-study-prep3-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY70_SUMMARY_PATH = "docs/artifacts/day70-case-study-prep2-closeout-pack/day70-case-study-prep2-closeout-summary.json"
_DAY70_BOARD_PATH = "docs/artifacts/day70-case-study-prep2-closeout-pack/day70-delivery-board.md"
_CASE_STUDY_DATA_PATH = ".day71-escalation-quality-case-study.json"
_SECTION_HEADER = "# Day 71 — Case-study prep #3 closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 71 matters",
    "## Required inputs (Day 70)",
    "## Day 71 command lane",
    "## Case-study prep contract",
    "## Case-study quality checklist",
    "## Day 71 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day71-case-study-prep3-closeout --format json --strict",
    "python -m sdetkit day71-case-study-prep3-closeout --emit-pack-dir docs/artifacts/day71-case-study-prep3-closeout-pack --format json --strict",
    "python -m sdetkit day71-case-study-prep3-closeout --execute --evidence-dir docs/artifacts/day71-case-study-prep3-closeout-pack/evidence --format json --strict",
    "python scripts/check_day71_case_study_prep3_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day71-case-study-prep3-closeout --format json --strict",
    "python -m sdetkit day71-case-study-prep3-closeout --emit-pack-dir docs/artifacts/day71-case-study-prep3-closeout-pack --format json --strict",
    "python scripts/check_day71_case_study_prep3_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 71 escalation-quality case-study prep and signoff.",
    "The Day 71 lane references Day 70 case-study prep outputs, governance decisions, and KPI continuity signals.",
    "Every Day 71 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 71 closeout records before/after escalation-quality deltas, evidence confidence notes, and Day 72 prep priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes baseline window, treatment window, and outlier handling notes",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures failure-rate delta, MTTR delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, case-study narrative, controls log, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 71 integration brief committed",
    "- [ ] Day 71 escalation-quality case-study narrative published",
    "- [ ] Day 71 controls and assumptions log exported",
    "- [ ] Day 71 KPI scorecard snapshot exported",
    "- [ ] Day 72 case-study prep priorities drafted from Day 71 learnings",
]
_REQUIRED_DATA_KEYS = [
    '"case_id"',
    '"metric"',
    '"baseline"',
    '"after"',
    '"confidence"',
    '"owner"',
]

_DAY71_DEFAULT_PAGE = """# Day 71 — Case-study prep #3 closeout lane

Day 71 closes with a major upgrade that turns Day 70 integration outputs into a measurable escalation-quality case-study prep pack.

## Why Day 71 matters

- Converts Day 70 implementation signals into before/after escalation-quality evidence.
- Protects case-study quality with strict contract coverage, runnable commands, and rollback safety.
- Creates a deterministic handoff from Day 71 case-study prep #3 to Day 72 case-study prep #4.

## Required inputs (Day 70)

- `docs/artifacts/day70-case-study-prep2-closeout-pack/day70-case-study-prep2-closeout-summary.json`
- `docs/artifacts/day70-case-study-prep2-closeout-pack/day70-delivery-board.md`
- `.day71-escalation-quality-case-study.json`

## Day 71 command lane

```bash
python -m sdetkit day71-case-study-prep3-closeout --format json --strict
python -m sdetkit day71-case-study-prep3-closeout --emit-pack-dir docs/artifacts/day71-case-study-prep3-closeout-pack --format json --strict
python -m sdetkit day71-case-study-prep3-closeout --execute --evidence-dir docs/artifacts/day71-case-study-prep3-closeout-pack/evidence --format json --strict
python scripts/check_day71_case_study_prep3_closeout_contract.py
```

## Case-study prep contract

- Single owner + backup reviewer are assigned for Day 71 escalation-quality case-study prep and signoff.
- The Day 71 lane references Day 70 case-study prep outputs, governance decisions, and KPI continuity signals.
- Every Day 71 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 71 closeout records before/after escalation-quality deltas, evidence confidence notes, and Day 72 prep priorities.

## Case-study quality checklist

- [ ] Includes baseline window, treatment window, and outlier handling notes
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures failure-rate delta, MTTR delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, case-study narrative, controls log, KPI scorecard, and execution log

## Day 71 delivery board

- [ ] Day 71 integration brief committed
- [ ] Day 71 escalation-quality case-study narrative published
- [ ] Day 71 controls and assumptions log exported
- [ ] Day 71 KPI scorecard snapshot exported
- [ ] Day 72 case-study prep priorities drafted from Day 71 learnings

## Scoring model

Day 71 weighted score (0-100):

- Contract + command lane integrity (35)
- Day 70 continuity baseline quality (35)
- Escalation-quality evidence data + delivery board completeness (30)

Strict pass requires score >= 95 and zero critical failures.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_day70(summary_path: Path) -> tuple[int, bool, int]:
    if not summary_path.exists():
        return 0, False, 0
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return 0, False, 0
    summary = payload.get("summary", {})
    checks = payload.get("checks", [])
    return int(summary.get("activation_score", 0)), bool(summary.get("strict_pass", False)), len(checks)


def _count_board_items(board_path: Path, anchor: str) -> tuple[int, bool]:
    if not board_path.exists():
        return 0, False
    text = board_path.read_text(encoding="utf-8")
    items = [line for line in text.splitlines() if line.strip().startswith("- [")]
    return len(items), (anchor in text)


def build_day71_case_study_prep3_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    case_data_text = _read(root / _CASE_STUDY_DATA_PATH)

    day70_summary = root / _DAY70_SUMMARY_PATH
    day70_board = root / _DAY70_BOARD_PATH
    day70_score, day70_strict, day70_check_count = _load_day70(day70_summary)
    board_count, board_has_day70 = _count_board_items(day70_board, "Day 70")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_case_data_keys = [x for x in _REQUIRED_DATA_KEYS if x not in case_data_text]

    checks: list[dict[str, Any]] = [
        {"check_id": "readme_day71_command", "weight": 7, "passed": ("day71-case-study-prep3-closeout" in readme_text), "evidence": "README day71 command lane"},
        {
            "check_id": "docs_index_day71_links",
            "weight": 8,
            "passed": ("day-71-big-upgrade-report.md" in docs_index_text and "integrations-day71-case-study-prep3-closeout.md" in docs_index_text),
            "evidence": "day-71-big-upgrade-report.md + integrations-day71-case-study-prep3-closeout.md",
        },
        {"check_id": "top10_day71_alignment", "weight": 5, "passed": ("Day 71" in top10_text and "Day 72" in top10_text), "evidence": "Day 71 + Day 72 strategy chain"},
        {"check_id": "day70_summary_present", "weight": 10, "passed": day70_summary.exists(), "evidence": str(day70_summary)},
        {"check_id": "day70_delivery_board_present", "weight": 7, "passed": day70_board.exists(), "evidence": str(day70_board)},
        {
            "check_id": "day70_quality_floor",
            "weight": 13,
            "passed": day70_strict and day70_score >= 95,
            "evidence": {"day70_score": day70_score, "strict_pass": day70_strict, "day70_checks": day70_check_count},
        },
        {
            "check_id": "day70_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day70,
            "evidence": {"board_items": board_count, "contains_day70": board_has_day70},
        },
        {"check_id": "page_header", "weight": 7, "passed": _SECTION_HEADER in page_text, "evidence": _SECTION_HEADER},
        {"check_id": "required_sections", "weight": 8, "passed": not missing_sections, "evidence": missing_sections or "all sections present"},
        {"check_id": "required_commands", "weight": 5, "passed": not missing_commands, "evidence": missing_commands or "all commands present"},
        {"check_id": "contract_lock", "weight": 5, "passed": not missing_contract_lines, "evidence": missing_contract_lines or "contract locked"},
        {"check_id": "quality_checklist_lock", "weight": 5, "passed": not missing_quality_lines, "evidence": missing_quality_lines or "quality checklist locked"},
        {"check_id": "delivery_board_lock", "weight": 5, "passed": not missing_board_items, "evidence": missing_board_items or "delivery board locked"},
        {"check_id": "case_study_data_present", "weight": 10, "passed": not missing_case_data_keys, "evidence": missing_case_data_keys or _CASE_STUDY_DATA_PATH},
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day70_summary.exists() or not day70_board.exists():
        critical_failures.append("day70_handoff_inputs")
    if not day70_strict:
        critical_failures.append("day70_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day70_strict:
        wins.append(f"Day 70 continuity is strict-pass with activation score={day70_score}.")
    else:
        misses.append("Day 70 strict continuity signal is missing.")
        handoff_actions.append("Re-run Day 70 closeout command and restore strict baseline before Day 71 lock.")

    if board_count >= 5 and board_has_day70:
        wins.append(f"Day 70 delivery board integrity validated with {board_count} checklist items.")
    else:
        misses.append("Day 70 delivery board integrity is incomplete (needs >=5 items and Day 70 anchors).")
        handoff_actions.append("Repair Day 70 delivery board entries to include Day 70 anchors.")

    if not missing_case_data_keys:
        wins.append("Day 71 escalation-quality case-study dataset is available for case-study prep execution.")
    else:
        misses.append("Day 71 escalation-quality case-study dataset is missing required keys.")
        handoff_actions.append("Update .day71-escalation-quality-case-study.json to restore required keys.")

    if not failed and not critical_failures:
        wins.append("Day 71 case-study prep #3 closeout lane is fully complete and ready for Day 72 case-study prep #4.")

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day71-case-study-prep3-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day70_summary": str(day70_summary.relative_to(root)) if day70_summary.exists() else str(day70_summary),
            "day70_delivery_board": str(day70_board.relative_to(root)) if day70_board.exists() else str(day70_board),
            "case_study_data": _CASE_STUDY_DATA_PATH,
        },
        "checks": checks,
        "rollup": {"day70_activation_score": day70_score, "day70_checks": day70_check_count, "day70_delivery_board_items": board_count},
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
        "Day 71 case-study prep #3 closeout summary",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
    ]
    return "\n".join(lines)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _emit_pack(root: Path, pack_dir: Path, payload: dict[str, Any]) -> None:
    target = pack_dir if pack_dir.is_absolute() else root / pack_dir
    _write(target / "day71-case-study-prep3-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day71-case-study-prep3-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day71-integration-brief.md", "# Day 71 integration brief\n")
    _write(target / "day71-case-study-narrative.md", "# Day 71 case-study narrative\n")
    _write(target / "day71-controls-log.json", json.dumps({"controls": []}, indent=2) + "\n")
    _write(target / "day71-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day71-execution-log.md", "# Day 71 execution log\n")
    _write(target / "day71-delivery-board.md", "\n".join(["# Day 71 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n")
    _write(target / "day71-validation-commands.md", "# Day 71 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n")


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    events: list[dict[str, Any]] = []
    out_dir = evidence_dir if evidence_dir.is_absolute() else root / evidence_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, command in enumerate(_EXECUTION_COMMANDS, start=1):
        result = subprocess.run(shlex.split(command), cwd=root, capture_output=True, text=True)
        event = {"command": command, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        events.append(event)
        _write(out_dir / f"command-{idx:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(out_dir / "day71-execution-summary.json", json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 71 case-study prep #3 closeout checks")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--write-default-doc", action="store_true")
    ns = parser.parse_args(argv)

    root = Path(ns.root).resolve()
    if ns.write_default_doc:
        _write(root / _PAGE_PATH, _DAY71_DEFAULT_PAGE)

    payload = build_day71_case_study_prep3_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = Path(ns.evidence_dir) if ns.evidence_dir else Path("docs/artifacts/day71-case-study-prep3-closeout-pack/evidence")
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
