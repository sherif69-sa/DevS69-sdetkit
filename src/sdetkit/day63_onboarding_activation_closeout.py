from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day63-onboarding-activation-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY62_SUMMARY_PATH = "docs/artifacts/day62-community-program-closeout-pack/day62-community-program-closeout-summary.json"
_DAY62_BOARD_PATH = "docs/artifacts/day62-community-program-closeout-pack/day62-delivery-board.md"
_SECTION_HEADER = "# Day 63 \u2014 Contributor onboarding activation closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 63 matters",
    "## Required inputs (Day 62)",
    "## Day 63 command lane",
    "## Onboarding activation contract",
    "## Onboarding quality checklist",
    "## Day 63 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day63-onboarding-activation-closeout --format json --strict",
    "python -m sdetkit day63-onboarding-activation-closeout --emit-pack-dir docs/artifacts/day63-onboarding-activation-closeout-pack --format json --strict",
    "python -m sdetkit day63-onboarding-activation-closeout --execute --evidence-dir docs/artifacts/day63-onboarding-activation-closeout-pack/evidence --format json --strict",
    "python scripts/check_day63_onboarding_activation_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day63-onboarding-activation-closeout --format json --strict",
    "python -m sdetkit day63-onboarding-activation-closeout --emit-pack-dir docs/artifacts/day63-onboarding-activation-closeout-pack --format json --strict",
    "python scripts/check_day63_onboarding_activation_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 63 onboarding activation execution and roadmap-voting facilitation.",
    "The Day 63 lane references Day 62 community-program outcomes, moderation guardrails, and KPI continuity evidence.",
    "Every Day 63 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 63 closeout records onboarding orientation flow, ownership handoff SOP, roadmap voting launch, and Day 64 pipeline priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes onboarding orientation path, mentor ownership model, and rollback trigger",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures activation conversion, mentor SLA, roadmap-vote participation, confidence, and recovery owner",
    "- [ ] Artifact pack includes onboarding brief, orientation script, ownership matrix, roadmap-vote brief, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 63 onboarding launch brief committed",
    "- [ ] Day 63 orientation script + ownership matrix published",
    "- [ ] Day 63 roadmap voting brief exported",
    "- [ ] Day 63 KPI scorecard snapshot exported",
    "- [ ] Day 64 contributor pipeline priorities drafted from Day 63 learnings",
]

_DAY63_DEFAULT_PAGE = """# Day 63 \u2014 Contributor onboarding activation closeout lane

Day 63 ships a major onboarding-activation upgrade that converts Day 62 community program evidence into deterministic onboarding ownership and roadmap-voting loops.

## Why Day 63 matters

- Converts Day 62 community trust baseline into repeatable onboarding activation and mentor ownership loops.
- Protects contributor onboarding outcomes with ownership, command proof, and rollback guardrails.
- Produces a deterministic handoff from Day 63 onboarding activation into Day 64 contributor pipeline acceleration.

## Required inputs (Day 62)

- `docs/artifacts/day62-community-program-closeout-pack/day62-community-program-closeout-summary.json`
- `docs/artifacts/day62-community-program-closeout-pack/day62-delivery-board.md`

## Day 63 command lane

```bash
python -m sdetkit day63-onboarding-activation-closeout --format json --strict
python -m sdetkit day63-onboarding-activation-closeout --emit-pack-dir docs/artifacts/day63-onboarding-activation-closeout-pack --format json --strict
python -m sdetkit day63-onboarding-activation-closeout --execute --evidence-dir docs/artifacts/day63-onboarding-activation-closeout-pack/evidence --format json --strict
python scripts/check_day63_onboarding_activation_closeout_contract.py
```

## Onboarding activation contract

- Single owner + backup reviewer are assigned for Day 63 onboarding activation execution and roadmap-voting facilitation.
- The Day 63 lane references Day 62 community-program outcomes, moderation guardrails, and KPI continuity evidence.
- Every Day 63 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 63 closeout records onboarding orientation flow, ownership handoff SOP, roadmap voting launch, and Day 64 pipeline priorities.

## Onboarding quality checklist

- [ ] Includes onboarding orientation path, mentor ownership model, and rollback trigger
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures activation conversion, mentor SLA, roadmap-vote participation, confidence, and recovery owner
- [ ] Artifact pack includes onboarding brief, orientation script, ownership matrix, roadmap-vote brief, and execution log

## Day 63 delivery board

- [ ] Day 63 onboarding launch brief committed
- [ ] Day 63 orientation script + ownership matrix published
- [ ] Day 63 roadmap voting brief exported
- [ ] Day 63 KPI scorecard snapshot exported
- [ ] Day 64 contributor pipeline priorities drafted from Day 63 learnings

## Scoring model

Day 63 weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 62 continuity and strict baseline carryover: 35 points.
- Onboarding activation contract lock + delivery board readiness: 15 points.
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


def _load_day62(path: Path) -> tuple[int, bool, int]:
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


def build_day63_onboarding_activation_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)

    day62_summary = root / _DAY62_SUMMARY_PATH
    day62_board = root / _DAY62_BOARD_PATH
    day62_score, day62_strict, day62_check_count = _load_day62(day62_summary)
    board_count, board_has_day62 = _count_board_items(day62_board, "Day 62")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day63_command",
            "weight": 7,
            "passed": ("day63-onboarding-activation-closeout" in readme_text),
            "evidence": "README day63 command lane",
        },
        {
            "check_id": "docs_index_day63_links",
            "weight": 8,
            "passed": (
                "day-63-big-upgrade-report.md" in docs_index_text
                and "integrations-day63-onboarding-activation-closeout.md" in docs_index_text
            ),
            "evidence": "day-63-big-upgrade-report.md + integrations-day63-onboarding-activation-closeout.md",
        },
        {
            "check_id": "top10_day63_alignment",
            "weight": 5,
            "passed": ("Day 63" in top10_text and "Day 64" in top10_text),
            "evidence": "Day 63 + Day 64 strategy chain",
        },
        {
            "check_id": "day62_summary_present",
            "weight": 10,
            "passed": day62_summary.exists(),
            "evidence": str(day62_summary),
        },
        {
            "check_id": "day62_delivery_board_present",
            "weight": 8,
            "passed": day62_board.exists(),
            "evidence": str(day62_board),
        },
        {
            "check_id": "day62_quality_floor",
            "weight": 15,
            "passed": day62_strict and day62_score >= 95,
            "evidence": {
                "day62_score": day62_score,
                "strict_pass": day62_strict,
                "day62_checks": day62_check_count,
            },
        },
        {
            "check_id": "day62_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day62,
            "evidence": {"board_items": board_count, "contains_day62": board_has_day62},
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
    if not day62_summary.exists() or not day62_board.exists():
        critical_failures.append("day62_handoff_inputs")
    if not day62_strict:
        critical_failures.append("day62_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day62_strict:
        wins.append(f"Day 62 continuity is strict-pass with activation score={day62_score}.")
    else:
        misses.append("Day 62 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 62 community-program closeout command and restore strict baseline before Day 63 lock."
        )

    if board_count >= 5 and board_has_day62:
        wins.append(
            f"Day 62 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 62 delivery board integrity is incomplete (needs >=5 items and Day 62 anchors)."
        )
        handoff_actions.append("Repair Day 62 delivery board entries to include Day 62 anchors.")

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Onboarding activation contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Onboarding activation contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 63 contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 63 onboarding activation closeout lane is fully complete and ready for Day 64 contributor pipeline lane."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day63-onboarding-activation-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day62_summary": str(day62_summary.relative_to(root))
            if day62_summary.exists()
            else str(day62_summary),
            "day62_delivery_board": str(day62_board.relative_to(root))
            if day62_board.exists()
            else str(day62_board),
        },
        "checks": checks,
        "rollup": {
            "day62_activation_score": day62_score,
            "day62_checks": day62_check_count,
            "day62_delivery_board_items": board_count,
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
        "Day 63 onboarding activation closeout summary",
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
        target / "day63-onboarding-activation-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "day63-onboarding-activation-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day63-onboarding-launch-brief.md", "# Day 63 onboarding launch brief\n")
    _write(target / "day63-orientation-script.md", "# Day 63 orientation script\n")
    _write(target / "day63-ownership-matrix.csv", "track,owner,backup,sla\n")
    _write(target / "day63-roadmap-voting-brief.md", "# Day 63 roadmap voting brief\n")
    _write(target / "day63-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day63-execution-log.md", "# Day 63 execution log\n")
    _write(
        target / "day63-delivery-board.md",
        "\n".join(["# Day 63 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day63-validation-commands.md",
        "# Day 63 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day63-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 63 onboarding activation closeout checks")
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
        _write(root / _PAGE_PATH, _DAY63_DEFAULT_PAGE)

    payload = build_day63_onboarding_activation_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day63-onboarding-activation-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
