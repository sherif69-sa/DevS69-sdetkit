from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day59-phase3-preplan-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY58_SUMMARY_PATH = "docs/artifacts/day58-phase2-hardening-closeout-pack/day58-phase2-hardening-closeout-summary.json"
_DAY58_BOARD_PATH = "docs/artifacts/day58-phase2-hardening-closeout-pack/day58-delivery-board.md"
_SECTION_HEADER = "# Day 59 \u2014 Phase-3 pre-plan closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 59 matters",
    "## Required inputs (Day 58)",
    "## Day 59 command lane",
    "## Phase-3 pre-plan contract",
    "## Phase-3 pre-plan quality checklist",
    "## Day 59 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day59-phase3-preplan-closeout --format json --strict",
    "python -m sdetkit day59-phase3-preplan-closeout --emit-pack-dir docs/artifacts/day59-phase3-preplan-closeout-pack --format json --strict",
    "python -m sdetkit day59-phase3-preplan-closeout --execute --evidence-dir docs/artifacts/day59-phase3-preplan-closeout-pack/evidence --format json --strict",
    "python scripts/check_day59_phase3_preplan_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day59-phase3-preplan-closeout --format json --strict",
    "python -m sdetkit day59-phase3-preplan-closeout --emit-pack-dir docs/artifacts/day59-phase3-preplan-closeout-pack --format json --strict",
    "python scripts/check_day59_phase3_preplan_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 59 Phase-3 pre-plan execution and signal triage.",
    "The Day 59 lane references Day 58 Phase-2 hardening outcomes and unresolved risks.",
    "Every Day 59 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 59 closeout records pre-plan outcomes and Day 60 execution priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes priority digest, lane-level plan actions, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI",
    "- [ ] Artifact pack includes pre-plan brief, risk ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 59 Phase-3 pre-plan brief committed",
    "- [ ] Day 59 pre-plan reviewed with owner + backup",
    "- [ ] Day 59 risk ledger exported",
    "- [ ] Day 59 KPI scorecard snapshot exported",
    "- [ ] Day 60 execution priorities drafted from Day 59 learnings",
]

_DAY59_DEFAULT_PAGE = """# Day 59 \u2014 Phase-3 pre-plan closeout lane

Day 59 closes with a major Phase-3 pre-plan upgrade that turns Day 58 hardening outcomes into deterministic Day 60 execution priorities.

## Why Day 59 matters

- Converts Day 58 hardening evidence into repeatable Phase-3 planning loops.
- Protects quality with ownership, command proof, and KPI rollback guardrails.
- Produces a deterministic handoff from Day 59 closeout into Day 60 execution planning.

## Required inputs (Day 58)

- `docs/artifacts/day58-phase2-hardening-closeout-pack/day58-phase2-hardening-closeout-summary.json`
- `docs/artifacts/day58-phase2-hardening-closeout-pack/day58-delivery-board.md`

## Day 59 command lane

```bash
python -m sdetkit day59-phase3-preplan-closeout --format json --strict
python -m sdetkit day59-phase3-preplan-closeout --emit-pack-dir docs/artifacts/day59-phase3-preplan-closeout-pack --format json --strict
python -m sdetkit day59-phase3-preplan-closeout --execute --evidence-dir docs/artifacts/day59-phase3-preplan-closeout-pack/evidence --format json --strict
python scripts/check_day59_phase3_preplan_closeout_contract.py
```

## Phase-3 pre-plan contract

- Single owner + backup reviewer are assigned for Day 59 Phase-3 pre-plan execution and signal triage.
- The Day 59 lane references Day 58 Phase-2 hardening outcomes and unresolved risks.
- Every Day 59 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 59 closeout records pre-plan outcomes and Day 60 execution priorities.

## Phase-3 pre-plan quality checklist

- [ ] Includes priority digest, lane-level plan actions, and rollback strategy
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI
- [ ] Artifact pack includes pre-plan brief, risk ledger, KPI scorecard, and execution log

## Day 59 delivery board

- [ ] Day 59 Phase-3 pre-plan brief committed
- [ ] Day 59 pre-plan reviewed with owner + backup
- [ ] Day 59 risk ledger exported
- [ ] Day 59 KPI scorecard snapshot exported
- [ ] Day 60 execution priorities drafted from Day 59 learnings

## Scoring model

Day 59 weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 58 continuity and strict baseline carryover: 35 points.
- Phase-3 pre-plan contract lock + delivery board readiness: 15 points.
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


def _load_day58(path: Path) -> tuple[int, bool, int]:
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


def build_day59_phase3_preplan_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)

    day58_summary = root / _DAY58_SUMMARY_PATH
    day58_board = root / _DAY58_BOARD_PATH
    day58_score, day58_strict, day58_check_count = _load_day58(day58_summary)
    board_count, board_has_day58 = _count_board_items(day58_board, "Day 58")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day59_command",
            "weight": 7,
            "passed": ("day59-phase3-preplan-closeout" in readme_text),
            "evidence": "README day59 command lane",
        },
        {
            "check_id": "docs_index_day59_links",
            "weight": 8,
            "passed": (
                "day-59-big-upgrade-report.md" in docs_index_text
                and "integrations-day59-phase3-preplan-closeout.md" in docs_index_text
            ),
            "evidence": "day-59-big-upgrade-report.md + integrations-day59-phase3-preplan-closeout.md",
        },
        {
            "check_id": "top10_day59_alignment",
            "weight": 5,
            "passed": ("Day 59" in top10_text and "Day 60" in top10_text),
            "evidence": "Day 59 + Day 60 strategy chain",
        },
        {
            "check_id": "day58_summary_present",
            "weight": 10,
            "passed": day58_summary.exists(),
            "evidence": str(day58_summary),
        },
        {
            "check_id": "day58_delivery_board_present",
            "weight": 8,
            "passed": day58_board.exists(),
            "evidence": str(day58_board),
        },
        {
            "check_id": "day58_quality_floor",
            "weight": 15,
            "passed": day58_strict and day58_score >= 95,
            "evidence": {
                "day58_score": day58_score,
                "strict_pass": day58_strict,
                "day58_checks": day58_check_count,
            },
        },
        {
            "check_id": "day58_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day58,
            "evidence": {"board_items": board_count, "contains_day58": board_has_day58},
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
    if not day58_summary.exists() or not day58_board.exists():
        critical_failures.append("day58_handoff_inputs")
    if not day58_strict:
        critical_failures.append("day58_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day58_strict:
        wins.append(f"Day 58 continuity is strict-pass with activation score={day58_score}.")
    else:
        misses.append("Day 58 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 58 Phase-2 hardening closeout command and restore strict baseline before Day 59 lock."
        )

    if board_count >= 5 and board_has_day58:
        wins.append(
            f"Day 58 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 58 delivery board integrity is incomplete (needs >=5 items and Day 58 anchors)."
        )
        handoff_actions.append("Repair Day 58 delivery board entries to include Day 58 anchors.")

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Phase-3 pre-plan contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Phase-3 pre-plan contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 59 contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 59 Phase-3 pre-plan closeout lane is fully complete and ready for Day 60 execution lane."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day59-phase3-preplan-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day58_summary": str(day58_summary.relative_to(root))
            if day58_summary.exists()
            else str(day58_summary),
            "day58_delivery_board": str(day58_board.relative_to(root))
            if day58_board.exists()
            else str(day58_board),
        },
        "checks": checks,
        "rollup": {
            "day58_activation_score": day58_score,
            "day58_checks": day58_check_count,
            "day58_delivery_board_items": board_count,
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
        "Day 59 Phase-3 pre-plan closeout summary",
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
        target / "day59-phase3-preplan-closeout-summary.json", json.dumps(payload, indent=2) + "\n"
    )
    _write(target / "day59-phase3-preplan-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day59-phase3-preplan-brief.md", "# Day 59 Phase-3 pre-plan brief\n")
    _write(target / "day59-risk-ledger.csv", "risk,owner,mitigation,status\n")
    _write(target / "day59-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day59-execution-log.md", "# Day 59 execution log\n")
    _write(
        target / "day59-delivery-board.md",
        "\n".join(["# Day 59 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day59-validation-commands.md",
        "# Day 59 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day59-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 59 Phase-3 pre-plan closeout checks")
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
        _write(root / _PAGE_PATH, _DAY59_DEFAULT_PAGE)

    payload = build_day59_phase3_preplan_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day59-phase3-preplan-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
