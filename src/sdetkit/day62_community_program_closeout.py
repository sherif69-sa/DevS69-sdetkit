from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day62-community-program-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY61_SUMMARY_PATH = (
    "docs/artifacts/day61-phase3-kickoff-closeout-pack/day61-phase3-kickoff-closeout-summary.json"
)
_DAY61_BOARD_PATH = "docs/artifacts/day61-phase3-kickoff-closeout-pack/day61-delivery-board.md"
_SECTION_HEADER = "# Day 62 \u2014 Community program setup closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 62 matters",
    "## Required inputs (Day 61)",
    "## Day 62 command lane",
    "## Community program execution contract",
    "## Community program quality checklist",
    "## Day 62 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day62-community-program-closeout --format json --strict",
    "python -m sdetkit day62-community-program-closeout --emit-pack-dir docs/artifacts/day62-community-program-closeout-pack --format json --strict",
    "python -m sdetkit day62-community-program-closeout --execute --evidence-dir docs/artifacts/day62-community-program-closeout-pack/evidence --format json --strict",
    "python scripts/check_day62_community_program_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day62-community-program-closeout --format json --strict",
    "python -m sdetkit day62-community-program-closeout --emit-pack-dir docs/artifacts/day62-community-program-closeout-pack --format json --strict",
    "python scripts/check_day62_community_program_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 62 community office-hours execution and moderation safety.",
    "The Day 62 lane references Day 61 Phase-3 kickoff outcomes, trust guardrails, and KPI continuity evidence.",
    "Every Day 62 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 62 closeout records office-hours cadence, participation rules, moderation SOPs, and Day 63 onboarding priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes office-hours calendar, participation policy, escalation flow, and rollback trigger",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures attendance target, response SLA, trust incidents, confidence, and recovery owner",
    "- [ ] Artifact pack includes launch brief, participation policy, moderation runbook, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 62 community launch brief committed",
    "- [ ] Day 62 office-hours cadence published",
    "- [ ] Day 62 participation policy + moderation SOP exported",
    "- [ ] Day 62 KPI scorecard snapshot exported",
    "- [ ] Day 63 onboarding priorities drafted from Day 62 learnings",
]

_DAY62_DEFAULT_PAGE = """# Day 62 \u2014 Community program setup closeout lane

Day 62 ships a major community-program upgrade that converts Day 61 kickoff evidence into a deterministic community operations lane.

## Why Day 62 matters

- Converts Day 61 trust baseline into repeatable office-hours and participation loops.
- Protects community trust outcomes with ownership, command proof, and moderation rollback guardrails.
- Produces a deterministic handoff from Day 62 community setup into Day 63 contributor onboarding activation.

## Required inputs (Day 61)

- `docs/artifacts/day61-phase3-kickoff-closeout-pack/day61-phase3-kickoff-closeout-summary.json`
- `docs/artifacts/day61-phase3-kickoff-closeout-pack/day61-delivery-board.md`

## Day 62 command lane

```bash
python -m sdetkit day62-community-program-closeout --format json --strict
python -m sdetkit day62-community-program-closeout --emit-pack-dir docs/artifacts/day62-community-program-closeout-pack --format json --strict
python -m sdetkit day62-community-program-closeout --execute --evidence-dir docs/artifacts/day62-community-program-closeout-pack/evidence --format json --strict
python scripts/check_day62_community_program_closeout_contract.py
```

## Community program execution contract

- Single owner + backup reviewer are assigned for Day 62 community office-hours execution and moderation safety.
- The Day 62 lane references Day 61 Phase-3 kickoff outcomes, trust guardrails, and KPI continuity evidence.
- Every Day 62 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 62 closeout records office-hours cadence, participation rules, moderation SOPs, and Day 63 onboarding priorities.

## Community program quality checklist

- [ ] Includes office-hours calendar, participation policy, escalation flow, and rollback trigger
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures attendance target, response SLA, trust incidents, confidence, and recovery owner
- [ ] Artifact pack includes launch brief, participation policy, moderation runbook, and execution log

## Day 62 delivery board

- [ ] Day 62 community launch brief committed
- [ ] Day 62 office-hours cadence published
- [ ] Day 62 participation policy + moderation SOP exported
- [ ] Day 62 KPI scorecard snapshot exported
- [ ] Day 63 onboarding priorities drafted from Day 62 learnings

## Scoring model

Day 62 weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 61 continuity and strict baseline carryover: 35 points.
- Community program contract lock + delivery board readiness: 15 points.
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


def _load_day61(path: Path) -> tuple[int, bool, int]:
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


def build_day62_community_program_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)

    day61_summary = root / _DAY61_SUMMARY_PATH
    day61_board = root / _DAY61_BOARD_PATH
    day61_score, day61_strict, day61_check_count = _load_day61(day61_summary)
    board_count, board_has_day61 = _count_board_items(day61_board, "Day 61")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day62_command",
            "weight": 7,
            "passed": ("day62-community-program-closeout" in readme_text),
            "evidence": "README day62 command lane",
        },
        {
            "check_id": "docs_index_day62_links",
            "weight": 8,
            "passed": (
                "day-62-big-upgrade-report.md" in docs_index_text
                and "integrations-day62-community-program-closeout.md" in docs_index_text
            ),
            "evidence": "day-62-big-upgrade-report.md + integrations-day62-community-program-closeout.md",
        },
        {
            "check_id": "top10_day62_alignment",
            "weight": 5,
            "passed": ("Day 62" in top10_text and "Day 63" in top10_text),
            "evidence": "Day 62 + Day 63 strategy chain",
        },
        {
            "check_id": "day61_summary_present",
            "weight": 10,
            "passed": day61_summary.exists(),
            "evidence": str(day61_summary),
        },
        {
            "check_id": "day61_delivery_board_present",
            "weight": 8,
            "passed": day61_board.exists(),
            "evidence": str(day61_board),
        },
        {
            "check_id": "day61_quality_floor",
            "weight": 15,
            "passed": day61_strict and day61_score >= 95,
            "evidence": {
                "day61_score": day61_score,
                "strict_pass": day61_strict,
                "day61_checks": day61_check_count,
            },
        },
        {
            "check_id": "day61_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day61,
            "evidence": {"board_items": board_count, "contains_day61": board_has_day61},
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
    if not day61_summary.exists() or not day61_board.exists():
        critical_failures.append("day61_handoff_inputs")
    if not day61_strict:
        critical_failures.append("day61_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day61_strict:
        wins.append(f"Day 61 continuity is strict-pass with activation score={day61_score}.")
    else:
        misses.append("Day 61 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 61 Phase-3 kickoff closeout command and restore strict baseline before Day 62 lock."
        )

    if board_count >= 5 and board_has_day61:
        wins.append(
            f"Day 61 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 61 delivery board integrity is incomplete (needs >=5 items and Day 61 anchors)."
        )
        handoff_actions.append("Repair Day 61 delivery board entries to include Day 61 anchors.")

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Community program contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Community program contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 62 contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 62 community program closeout lane is fully complete and ready for Day 63 onboarding execution lane."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day62-community-program-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day61_summary": str(day61_summary.relative_to(root))
            if day61_summary.exists()
            else str(day61_summary),
            "day61_delivery_board": str(day61_board.relative_to(root))
            if day61_board.exists()
            else str(day61_board),
        },
        "checks": checks,
        "rollup": {
            "day61_activation_score": day61_score,
            "day61_checks": day61_check_count,
            "day61_delivery_board_items": board_count,
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
        "Day 62 community program closeout summary",
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
        target / "day62-community-program-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "day62-community-program-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day62-community-launch-brief.md", "# Day 62 community launch brief\n")
    _write(
        target / "day62-office-hours-cadence.md",
        "# Day 62 office-hours cadence\n\n- Weekly office hours\n",
    )
    _write(target / "day62-participation-policy.md", "# Day 62 participation policy\n")
    _write(target / "day62-moderation-runbook.md", "# Day 62 moderation runbook\n")
    _write(target / "day62-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day62-execution-log.md", "# Day 62 execution log\n")
    _write(
        target / "day62-delivery-board.md",
        "\n".join(["# Day 62 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day62-validation-commands.md",
        "# Day 62 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day62-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 62 community program closeout checks")
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
        _write(root / _PAGE_PATH, _DAY62_DEFAULT_PAGE)

    payload = build_day62_community_program_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day62-community-program-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
