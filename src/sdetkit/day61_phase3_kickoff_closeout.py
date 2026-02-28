from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day61-phase3-kickoff-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY60_SUMMARY_PATH = "docs/artifacts/day60-phase2-wrap-handoff-closeout-pack/day60-phase2-wrap-handoff-closeout-summary.json"
_DAY60_BOARD_PATH = "docs/artifacts/day60-phase2-wrap-handoff-closeout-pack/day60-delivery-board.md"
_SECTION_HEADER = "# Day 61 \u2014 Phase-3 kickoff execution closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 61 matters",
    "## Required inputs (Day 60)",
    "## Day 61 command lane",
    "## Phase-3 kickoff execution contract",
    "## Phase-3 kickoff quality checklist",
    "## Day 61 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day61-phase3-kickoff-closeout --format json --strict",
    "python -m sdetkit day61-phase3-kickoff-closeout --emit-pack-dir docs/artifacts/day61-phase3-kickoff-closeout-pack --format json --strict",
    "python -m sdetkit day61-phase3-kickoff-closeout --execute --evidence-dir docs/artifacts/day61-phase3-kickoff-closeout-pack/evidence --format json --strict",
    "python scripts/check_day61_phase3_kickoff_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day61-phase3-kickoff-closeout --format json --strict",
    "python -m sdetkit day61-phase3-kickoff-closeout --emit-pack-dir docs/artifacts/day61-phase3-kickoff-closeout-pack --format json --strict",
    "python scripts/check_day61_phase3_kickoff_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 61 Phase-3 kickoff execution and trust-signal triage.",
    "The Day 61 lane references Day 60 Phase-2 wrap outcomes, risks, and KPI continuity evidence.",
    "Every Day 61 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 61 closeout records Phase-3 baseline activation, trust KPI owners, and Day 62 community program priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes baseline snapshot, owner map, KPI guardrails, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each trust KPI",
    "- [ ] Artifact pack includes kickoff brief, trust ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 61 Phase-3 kickoff brief committed",
    "- [ ] Day 61 kickoff reviewed with owner + backup",
    "- [ ] Day 61 trust ledger exported",
    "- [ ] Day 61 KPI scorecard snapshot exported",
    "- [ ] Day 62 community program priorities drafted from Day 61 learnings",
]

_DAY61_DEFAULT_PAGE = """# Day 61 \u2014 Phase-3 kickoff execution closeout lane

Day 61 ships a major Phase-3 kickoff upgrade that converts Day 60 wrap evidence into a strict baseline for ecosystem + trust execution.

## Why Day 61 matters

- Converts Day 60 closeout evidence into repeatable Phase-3 execution loops.
- Protects trust outcomes with ownership, command proof, and KPI rollback guardrails.
- Produces a deterministic handoff from Day 61 kickoff into Day 62 community program setup.

## Required inputs (Day 60)

- `docs/artifacts/day60-phase2-wrap-handoff-closeout-pack/day60-phase2-wrap-handoff-closeout-summary.json`
- `docs/artifacts/day60-phase2-wrap-handoff-closeout-pack/day60-delivery-board.md`

## Day 61 command lane

```bash
python -m sdetkit day61-phase3-kickoff-closeout --format json --strict
python -m sdetkit day61-phase3-kickoff-closeout --emit-pack-dir docs/artifacts/day61-phase3-kickoff-closeout-pack --format json --strict
python -m sdetkit day61-phase3-kickoff-closeout --execute --evidence-dir docs/artifacts/day61-phase3-kickoff-closeout-pack/evidence --format json --strict
python scripts/check_day61_phase3_kickoff_closeout_contract.py
```

## Phase-3 kickoff execution contract

- Single owner + backup reviewer are assigned for Day 61 Phase-3 kickoff execution and trust-signal triage.
- The Day 61 lane references Day 60 Phase-2 wrap outcomes, risks, and KPI continuity evidence.
- Every Day 61 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 61 closeout records Phase-3 baseline activation, trust KPI owners, and Day 62 community program priorities.

## Phase-3 kickoff quality checklist

- [ ] Includes baseline snapshot, owner map, KPI guardrails, and rollback strategy
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each trust KPI
- [ ] Artifact pack includes kickoff brief, trust ledger, KPI scorecard, and execution log

## Day 61 delivery board

- [ ] Day 61 Phase-3 kickoff brief committed
- [ ] Day 61 kickoff reviewed with owner + backup
- [ ] Day 61 trust ledger exported
- [ ] Day 61 KPI scorecard snapshot exported
- [ ] Day 62 community program priorities drafted from Day 61 learnings

## Scoring model

Day 61 weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 60 continuity and strict baseline carryover: 35 points.
- Phase-3 kickoff contract lock + delivery board readiness: 15 points.
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


def _load_day60(path: Path) -> tuple[int, bool, int]:
    payload_obj = _load_json(path)
    if not isinstance(payload_obj, dict):
        return 0, False, 0
    summary_obj = payload_obj.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    score = int(summary.get("activation_score", 0))
    strict = bool(summary.get("strict_pass", False))
    checks_obj = payload_obj.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    return score, strict, len(checks)


def _count_board_items(path: Path, needle: str) -> tuple[int, bool]:
    text = _read(path)
    lines = [ln.strip() for ln in text.splitlines()]
    checks = [ln for ln in lines if ln.startswith("- [")]
    return len(checks), (needle in text)


def build_day61_phase3_kickoff_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)

    day60_summary = root / _DAY60_SUMMARY_PATH
    day60_board = root / _DAY60_BOARD_PATH
    day60_score, day60_strict, day60_check_count = _load_day60(day60_summary)
    board_count, board_has_day60 = _count_board_items(day60_board, "Day 60")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day61_command",
            "weight": 7,
            "passed": ("day61-phase3-kickoff-closeout" in readme_text),
            "evidence": "README day61 command lane",
        },
        {
            "check_id": "docs_index_day61_links",
            "weight": 8,
            "passed": (
                "day-61-big-upgrade-report.md" in docs_index_text
                and "integrations-day61-phase3-kickoff-closeout.md" in docs_index_text
            ),
            "evidence": "day-61-big-upgrade-report.md + integrations-day61-phase3-kickoff-closeout.md",
        },
        {
            "check_id": "top10_day61_alignment",
            "weight": 5,
            "passed": ("Day 61" in top10_text and "Day 62" in top10_text),
            "evidence": "Day 61 + Day 62 strategy chain",
        },
        {
            "check_id": "day60_summary_present",
            "weight": 10,
            "passed": day60_summary.exists(),
            "evidence": str(day60_summary),
        },
        {
            "check_id": "day60_delivery_board_present",
            "weight": 8,
            "passed": day60_board.exists(),
            "evidence": str(day60_board),
        },
        {
            "check_id": "day60_quality_floor",
            "weight": 15,
            "passed": day60_strict and day60_score >= 95,
            "evidence": {
                "day60_score": day60_score,
                "strict_pass": day60_strict,
                "day60_checks": day60_check_count,
            },
        },
        {
            "check_id": "day60_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day60,
            "evidence": {"board_items": board_count, "contains_day60": board_has_day60},
        },
        {
            "check_id": "page_header",
            "weight": 7,
            "passed": _SECTION_HEADER in page_text,
            "evidence": _SECTION_HEADER,
        },
        {
            "check_id": "required_sections",
            "weight": 10,
            "passed": not missing_sections,
            "evidence": missing_sections or "all sections present",
        },
        {
            "check_id": "required_commands",
            "weight": 8,
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
            "weight": 3,
            "passed": not missing_quality_lines,
            "evidence": missing_quality_lines or "quality checklist locked",
        },
        {
            "check_id": "delivery_board_lock",
            "weight": 2,
            "passed": not missing_board_items,
            "evidence": missing_board_items or "delivery board locked",
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day60_summary.exists() or not day60_board.exists():
        critical_failures.append("day60_handoff_inputs")
    if not day60_strict:
        critical_failures.append("day60_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day60_strict:
        wins.append(f"Day 60 continuity is strict-pass with activation score={day60_score}.")
    else:
        misses.append("Day 60 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 60 Phase-2 wrap + handoff closeout command and restore strict baseline before Day 61 lock."
        )

    if board_count >= 5 and board_has_day60:
        wins.append(
            f"Day 60 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 60 delivery board integrity is incomplete (needs >=5 items and Day 60 anchors)."
        )
        handoff_actions.append("Repair Day 60 delivery board entries to include Day 60 anchors.")

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Phase-3 kickoff contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Phase-3 kickoff contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 61 contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 61 Phase-3 kickoff closeout lane is fully complete and ready for Day 62 community execution lane."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day61-phase3-kickoff-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day60_summary": str(day60_summary.relative_to(root))
            if day60_summary.exists()
            else str(day60_summary),
            "day60_delivery_board": str(day60_board.relative_to(root))
            if day60_board.exists()
            else str(day60_board),
        },
        "checks": checks,
        "rollup": {
            "day60_activation_score": day60_score,
            "day60_checks": day60_check_count,
            "day60_delivery_board_items": board_count,
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
        "Day 61 Phase-3 kickoff closeout summary",
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
        target / "day61-phase3-kickoff-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "day61-phase3-kickoff-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day61-phase3-kickoff-brief.md", "# Day 61 Phase-3 kickoff brief\n")
    _write(target / "day61-trust-ledger.csv", "risk,owner,mitigation,status\n")
    _write(target / "day61-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day61-execution-log.md", "# Day 61 execution log\n")
    _write(
        target / "day61-delivery-board.md",
        "\n".join(["# Day 61 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day61-validation-commands.md",
        "# Day 61 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day61-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 61 Phase-3 kickoff closeout checks")
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
        _write(root / _PAGE_PATH, _DAY61_DEFAULT_PAGE)

    payload = build_day61_phase3_kickoff_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day61-phase3-kickoff-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
