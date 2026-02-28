from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day73-case-study-launch-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY72_SUMMARY_PATH = "docs/artifacts/day72-case-study-prep4-closeout-pack/day72-case-study-prep4-closeout-summary.json"
_DAY72_BOARD_PATH = "docs/artifacts/day72-case-study-prep4-closeout-pack/day72-delivery-board.md"
_CASE_STUDY_DATA_PATH = ".day73-published-case-study.json"
_SECTION_HEADER = "# Day 73 \u2014 Case-study launch closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 73 matters",
    "## Required inputs (Day 72)",
    "## Day 73 command lane",
    "## Case-study launch contract",
    "## Case-study quality checklist",
    "## Day 73 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day73-case-study-launch-closeout --format json --strict",
    "python -m sdetkit day73-case-study-launch-closeout --emit-pack-dir docs/artifacts/day73-case-study-launch-closeout-pack --format json --strict",
    "python -m sdetkit day73-case-study-launch-closeout --execute --evidence-dir docs/artifacts/day73-case-study-launch-closeout-pack/evidence --format json --strict",
    "python scripts/check_day73_case_study_launch_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day73-case-study-launch-closeout --format json --strict",
    "python -m sdetkit day73-case-study-launch-closeout --emit-pack-dir docs/artifacts/day73-case-study-launch-closeout-pack --format json --strict",
    "python scripts/check_day73_case_study_launch_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 73 published case-study launch execution and signoff.",
    "The Day 73 lane references Day 72 prep outputs, governance decisions, and KPI continuity signals.",
    "Every Day 73 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 73 closeout records publication outcomes, evidence confidence notes, and Day 74 scaling priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes baseline window, treatment window, and outlier handling notes",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures failure-rate delta, MTTR delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, case-study narrative, controls log, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 73 integration brief committed",
    "- [ ] Day 73 published case-study narrative committed",
    "- [ ] Day 73 controls and assumptions log exported",
    "- [ ] Day 73 KPI scorecard snapshot exported",
    "- [ ] Day 74 distribution scaling priorities drafted from Day 73 learnings",
]
_REQUIRED_DATA_KEYS = [
    '"case_id"',
    '"metric"',
    '"baseline"',
    '"after"',
    '"confidence"',
    '"owner"',
]

_DAY73_DEFAULT_PAGE = """# Day 73 \u2014 Case-study launch closeout lane

Day 73 closes with a major upgrade that turns Day 72 publication-quality prep into a published case-study launch pack with rollout safeguards.

## Why Day 73 matters

- Converts Day 72 prep outputs into published case-study assets tied to measurable incident-response outcomes.
- Protects publication quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.
- Creates a deterministic handoff from Day 73 publication launch execution into Day 74 distribution scaling.

## Required inputs (Day 72)

- `docs/artifacts/day72-case-study-prep4-closeout-pack/day72-case-study-prep4-closeout-summary.json`
- `docs/artifacts/day72-case-study-prep4-closeout-pack/day72-delivery-board.md`
- `.day73-published-case-study.json`

## Day 73 command lane

```bash
python -m sdetkit day73-case-study-launch-closeout --format json --strict
python -m sdetkit day73-case-study-launch-closeout --emit-pack-dir docs/artifacts/day73-case-study-launch-closeout-pack --format json --strict
python -m sdetkit day73-case-study-launch-closeout --execute --evidence-dir docs/artifacts/day73-case-study-launch-closeout-pack/evidence --format json --strict
python scripts/check_day73_case_study_launch_closeout_contract.py
```

## Case-study launch contract

- Single owner + backup reviewer are assigned for Day 73 published case-study launch execution and signoff.
- The Day 73 lane references Day 72 prep outputs, governance decisions, and KPI continuity signals.
- Every Day 73 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 73 closeout records publication outcomes, evidence confidence notes, and Day 74 scaling priorities.

## Case-study quality checklist

- [ ] Includes baseline window, treatment window, and outlier handling notes
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures failure-rate delta, MTTR delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, case-study narrative, controls log, KPI scorecard, and execution log

## Day 73 delivery board

- [ ] Day 73 integration brief committed
- [ ] Day 73 published case-study narrative committed
- [ ] Day 73 controls and assumptions log exported
- [ ] Day 73 KPI scorecard snapshot exported
- [ ] Day 74 distribution scaling priorities drafted from Day 73 learnings

## Scoring model

Day 73 weighted score (0-100):

- Contract + command lane integrity (35)
- Day 72 continuity baseline quality (35)
- Publication-quality evidence data + delivery board completeness (30)

Strict pass requires score >= 95 and zero critical failures.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_day72(summary_path: Path) -> tuple[int, bool, int]:
    if not summary_path.exists():
        return 0, False, 0
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return 0, False, 0
    summary = payload.get("summary", {})
    checks = payload.get("checks", [])
    return (
        int(summary.get("activation_score", 0)),
        bool(summary.get("strict_pass", False)),
        len(checks),
    )


def _count_board_items(board_path: Path, anchor: str) -> tuple[int, bool]:
    if not board_path.exists():
        return 0, False
    text = board_path.read_text(encoding="utf-8")
    items = [line for line in text.splitlines() if line.strip().startswith("- [")]
    return len(items), (anchor in text)


def build_day73_case_study_launch_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    case_data_text = _read(root / _CASE_STUDY_DATA_PATH)

    day72_summary = root / _DAY72_SUMMARY_PATH
    day72_board = root / _DAY72_BOARD_PATH
    day72_score, day72_strict, day72_check_count = _load_day72(day72_summary)
    board_count, board_has_day72 = _count_board_items(day72_board, "Day 72")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_case_data_keys = [x for x in _REQUIRED_DATA_KEYS if x not in case_data_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day73_command",
            "weight": 7,
            "passed": ("day73-case-study-launch-closeout" in readme_text),
            "evidence": "README day73 command lane",
        },
        {
            "check_id": "docs_index_day73_links",
            "weight": 8,
            "passed": (
                "day-73-big-upgrade-report.md" in docs_index_text
                and "integrations-day73-case-study-launch-closeout.md" in docs_index_text
            ),
            "evidence": "day-73-big-upgrade-report.md + integrations-day73-case-study-launch-closeout.md",
        },
        {
            "check_id": "top10_day73_alignment",
            "weight": 5,
            "passed": ("Day 73" in top10_text and "Day 74" in top10_text),
            "evidence": "Day 73 + Day 74 strategy chain",
        },
        {
            "check_id": "day72_summary_present",
            "weight": 10,
            "passed": day72_summary.exists(),
            "evidence": str(day72_summary),
        },
        {
            "check_id": "day72_delivery_board_present",
            "weight": 7,
            "passed": day72_board.exists(),
            "evidence": str(day72_board),
        },
        {
            "check_id": "day72_quality_floor",
            "weight": 13,
            "passed": day72_strict and day72_score >= 95,
            "evidence": {
                "day72_score": day72_score,
                "strict_pass": day72_strict,
                "day72_checks": day72_check_count,
            },
        },
        {
            "check_id": "day72_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day72,
            "evidence": {"board_items": board_count, "contains_day72": board_has_day72},
        },
        {
            "check_id": "page_header",
            "weight": 7,
            "passed": _SECTION_HEADER in page_text,
            "evidence": _SECTION_HEADER,
        },
        {
            "check_id": "required_sections",
            "weight": 8,
            "passed": not missing_sections,
            "evidence": missing_sections or "all sections present",
        },
        {
            "check_id": "required_commands",
            "weight": 5,
            "passed": not missing_commands,
            "evidence": missing_commands or "all commands present",
        },
        {
            "check_id": "contract_lock",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": missing_contract_lines or "contract locked",
        },
        {
            "check_id": "quality_checklist_lock",
            "weight": 5,
            "passed": not missing_quality_lines,
            "evidence": missing_quality_lines or "quality checklist locked",
        },
        {
            "check_id": "delivery_board_lock",
            "weight": 5,
            "passed": not missing_board_items,
            "evidence": missing_board_items or "delivery board locked",
        },
        {
            "check_id": "case_study_data_present",
            "weight": 10,
            "passed": not missing_case_data_keys,
            "evidence": missing_case_data_keys or _CASE_STUDY_DATA_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day72_summary.exists() or not day72_board.exists():
        critical_failures.append("day72_handoff_inputs")
    if not day72_strict:
        critical_failures.append("day72_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day72_strict:
        wins.append(f"Day 72 continuity is strict-pass with activation score={day72_score}.")
    else:
        misses.append("Day 72 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 72 closeout command and restore strict baseline before Day 73 lock."
        )

    if board_count >= 5 and board_has_day72:
        wins.append(
            f"Day 72 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 72 delivery board integrity is incomplete (needs >=5 items and Day 72 anchors)."
        )
        handoff_actions.append("Repair Day 72 delivery board entries to include Day 72 anchors.")

    if not missing_case_data_keys:
        wins.append("Day 73 published case-study dataset is available for launch execution.")
    else:
        misses.append("Day 73 published case-study dataset is missing required keys.")
        handoff_actions.append("Update .day73-published-case-study.json to restore required keys.")

    if not failed and not critical_failures:
        wins.append(
            "Day 73 case-study launch closeout lane is fully complete and ready for Day 74 distribution scaling."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day73-case-study-launch-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day72_summary": str(day72_summary.relative_to(root))
            if day72_summary.exists()
            else str(day72_summary),
            "day72_delivery_board": str(day72_board.relative_to(root))
            if day72_board.exists()
            else str(day72_board),
            "case_study_data": _CASE_STUDY_DATA_PATH,
        },
        "checks": checks,
        "rollup": {
            "day72_activation_score": day72_score,
            "day72_checks": day72_check_count,
            "day72_delivery_board_items": board_count,
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
        "Day 73 case-study launch closeout summary",
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
    _write(
        target / "day73-case-study-launch-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "day73-case-study-launch-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day73-integration-brief.md", "# Day 73 integration brief\n")
    _write(target / "day73-case-study-narrative.md", "# Day 73 case-study narrative\n")
    _write(target / "day73-controls-log.json", json.dumps({"controls": []}, indent=2) + "\n")
    _write(target / "day73-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day73-execution-log.md", "# Day 73 execution log\n")
    _write(
        target / "day73-delivery-board.md",
        "\n".join(["# Day 73 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day73-validation-commands.md",
        "# Day 73 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    events: list[dict[str, Any]] = []
    out_dir = evidence_dir if evidence_dir.is_absolute() else root / evidence_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, command in enumerate(_EXECUTION_COMMANDS, start=1):
        argv = shlex.split(command)
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
        event = {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        events.append(event)
        _write(out_dir / f"command-{idx:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        out_dir / "day73-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 73 case-study launch closeout checks")
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
        _write(root / _PAGE_PATH, _DAY73_DEFAULT_PAGE)

    payload = build_day73_case_study_launch_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day73-case-study-launch-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
