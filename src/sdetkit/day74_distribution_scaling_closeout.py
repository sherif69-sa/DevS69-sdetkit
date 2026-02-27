from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day74-distribution-scaling-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY73_SUMMARY_PATH = "docs/artifacts/day73-case-study-launch-closeout-pack/day73-case-study-launch-closeout-summary.json"
_DAY73_BOARD_PATH = "docs/artifacts/day73-case-study-launch-closeout-pack/day73-delivery-board.md"
_SCALING_PLAN_PATH = ".day74-distribution-scaling-plan.json"
_SECTION_HEADER = "# Day 74 — Distribution scaling closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 74 matters",
    "## Required inputs (Day 73)",
    "## Day 74 command lane",
    "## Distribution scaling contract",
    "## Distribution quality checklist",
    "## Day 74 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day74-distribution-scaling-closeout --format json --strict",
    "python -m sdetkit day74-distribution-scaling-closeout --emit-pack-dir docs/artifacts/day74-distribution-scaling-closeout-pack --format json --strict",
    "python -m sdetkit day74-distribution-scaling-closeout --execute --evidence-dir docs/artifacts/day74-distribution-scaling-closeout-pack/evidence --format json --strict",
    "python scripts/check_day74_distribution_scaling_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day74-distribution-scaling-closeout --format json --strict",
    "python -m sdetkit day74-distribution-scaling-closeout --emit-pack-dir docs/artifacts/day74-distribution-scaling-closeout-pack --format json --strict",
    "python scripts/check_day74_distribution_scaling_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 74 distribution scaling execution and signoff.",
    "The Day 74 lane references Day 73 publication outcomes, controls, and KPI continuity signals.",
    "Every Day 74 section includes channel CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 74 closeout records distribution outcomes, confidence notes, and Day 75 trust refresh priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes channel mix baseline, treatment cadence, and audience-segment assumptions",
    "- [ ] Every channel plan row has owner, launch window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures CTR delta, qualified lead delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, scaling plan, controls log, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 74 integration brief committed",
    "- [ ] Day 74 distribution scaling plan committed",
    "- [ ] Day 74 channel controls and assumptions log exported",
    "- [ ] Day 74 KPI scorecard snapshot exported",
    "- [ ] Day 75 trust refresh priorities drafted from Day 74 learnings",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"channels"',
    '"baseline"',
    '"target"',
    '"confidence"',
    '"owner"',
]

_DAY74_DEFAULT_PAGE = """# Day 74 — Distribution scaling closeout lane

Day 74 closes with a major upgrade that turns Day 73 published case-study outcomes into a scalable distribution execution pack with governance safeguards.

## Why Day 74 matters

- Converts Day 73 publication proof into repeatable multi-channel distribution operations.
- Protects scaling quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.
- Creates a deterministic handoff from Day 74 distribution scaling execution into Day 75 trust-asset refresh.

## Required inputs (Day 73)

- `docs/artifacts/day73-case-study-launch-closeout-pack/day73-case-study-launch-closeout-summary.json`
- `docs/artifacts/day73-case-study-launch-closeout-pack/day73-delivery-board.md`
- `.day74-distribution-scaling-plan.json`

## Day 74 command lane

```bash
python -m sdetkit day74-distribution-scaling-closeout --format json --strict
python -m sdetkit day74-distribution-scaling-closeout --emit-pack-dir docs/artifacts/day74-distribution-scaling-closeout-pack --format json --strict
python -m sdetkit day74-distribution-scaling-closeout --execute --evidence-dir docs/artifacts/day74-distribution-scaling-closeout-pack/evidence --format json --strict
python scripts/check_day74_distribution_scaling_closeout_contract.py
```

## Distribution scaling contract

- Single owner + backup reviewer are assigned for Day 74 distribution scaling execution and signoff.
- The Day 74 lane references Day 73 publication outcomes, controls, and KPI continuity signals.
- Every Day 74 section includes channel CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 74 closeout records distribution outcomes, confidence notes, and Day 75 trust refresh priorities.

## Distribution quality checklist

- [ ] Includes channel mix baseline, treatment cadence, and audience-segment assumptions
- [ ] Every channel plan row has owner, launch window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures CTR delta, qualified lead delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, scaling plan, controls log, KPI scorecard, and execution log

## Day 74 delivery board

- [ ] Day 74 integration brief committed
- [ ] Day 74 distribution scaling plan committed
- [ ] Day 74 channel controls and assumptions log exported
- [ ] Day 74 KPI scorecard snapshot exported
- [ ] Day 75 trust refresh priorities drafted from Day 74 learnings

## Scoring model

Day 74 weighted score (0-100):

- Contract + command lane integrity (35)
- Day 73 continuity baseline quality (35)
- Distribution evidence data + delivery board completeness (30)

Strict pass requires score >= 95 and zero critical failures.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_day73(summary_path: Path) -> tuple[int, bool, int]:
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


def build_day74_distribution_scaling_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    scaling_plan_text = _read(root / _SCALING_PLAN_PATH)

    day73_summary = root / _DAY73_SUMMARY_PATH
    day73_board = root / _DAY73_BOARD_PATH
    day73_score, day73_strict, day73_check_count = _load_day73(day73_summary)
    board_count, board_has_day73 = _count_board_items(day73_board, "Day 73")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_scaling_plan_keys = [x for x in _REQUIRED_DATA_KEYS if x not in scaling_plan_text]

    checks: list[dict[str, Any]] = [
        {"check_id": "readme_day74_command", "weight": 7, "passed": ("day74-distribution-scaling-closeout" in readme_text), "evidence": "README day74 command lane"},
        {
            "check_id": "docs_index_day74_links",
            "weight": 8,
            "passed": ("day-74-big-upgrade-report.md" in docs_index_text and "integrations-day74-distribution-scaling-closeout.md" in docs_index_text),
            "evidence": "day-74-big-upgrade-report.md + integrations-day74-distribution-scaling-closeout.md",
        },
        {"check_id": "top10_day74_alignment", "weight": 5, "passed": ("Day 74" in top10_text and "Day 75" in top10_text), "evidence": "Day 74 + Day 75 strategy chain"},
        {"check_id": "day73_summary_present", "weight": 10, "passed": day73_summary.exists(), "evidence": str(day73_summary)},
        {"check_id": "day73_delivery_board_present", "weight": 7, "passed": day73_board.exists(), "evidence": str(day73_board)},
        {
            "check_id": "day73_quality_floor",
            "weight": 13,
            "passed": day73_strict and day73_score >= 95,
            "evidence": {"day73_score": day73_score, "strict_pass": day73_strict, "day73_checks": day73_check_count},
        },
        {
            "check_id": "day73_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day73,
            "evidence": {"board_items": board_count, "contains_day73": board_has_day73},
        },
        {"check_id": "page_header", "weight": 7, "passed": _SECTION_HEADER in page_text, "evidence": _SECTION_HEADER},
        {"check_id": "required_sections", "weight": 8, "passed": not missing_sections, "evidence": missing_sections or "all sections present"},
        {"check_id": "required_commands", "weight": 5, "passed": not missing_commands, "evidence": missing_commands or "all commands present"},
        {"check_id": "contract_lock", "weight": 5, "passed": not missing_contract_lines, "evidence": missing_contract_lines or "contract locked"},
        {"check_id": "quality_checklist_lock", "weight": 5, "passed": not missing_quality_lines, "evidence": missing_quality_lines or "quality checklist locked"},
        {"check_id": "delivery_board_lock", "weight": 5, "passed": not missing_board_items, "evidence": missing_board_items or "delivery board locked"},
        {"check_id": "distribution_plan_data_present", "weight": 10, "passed": not missing_scaling_plan_keys, "evidence": missing_scaling_plan_keys or _SCALING_PLAN_PATH},
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day73_summary.exists() or not day73_board.exists():
        critical_failures.append("day73_handoff_inputs")
    if not day73_strict:
        critical_failures.append("day73_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day73_strict:
        wins.append(f"Day 73 continuity is strict-pass with activation score={day73_score}.")
    else:
        misses.append("Day 73 strict continuity signal is missing.")
        handoff_actions.append("Re-run Day 73 closeout command and restore strict baseline before Day 74 lock.")

    if board_count >= 5 and board_has_day73:
        wins.append(f"Day 73 delivery board integrity validated with {board_count} checklist items.")
    else:
        misses.append("Day 73 delivery board integrity is incomplete (needs >=5 items and Day 73 anchors).")
        handoff_actions.append("Repair Day 73 delivery board entries to include Day 73 anchors.")

    if not missing_scaling_plan_keys:
        wins.append("Day 74 distribution scaling dataset is available for launch execution.")
    else:
        misses.append("Day 74 distribution scaling dataset is missing required keys.")
        handoff_actions.append("Update .day74-distribution-scaling-plan.json to restore required keys.")

    if not failed and not critical_failures:
        wins.append("Day 74 distribution scaling closeout lane is fully complete and ready for Day 75 trust refresh.")

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day74-distribution-scaling-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day73_summary": str(day73_summary.relative_to(root)) if day73_summary.exists() else str(day73_summary),
            "day73_delivery_board": str(day73_board.relative_to(root)) if day73_board.exists() else str(day73_board),
            "distribution_scaling_plan": _SCALING_PLAN_PATH,
        },
        "checks": checks,
        "rollup": {"day73_activation_score": day73_score, "day73_checks": day73_check_count, "day73_delivery_board_items": board_count},
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
        "Day 74 distribution scaling closeout summary",
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
    _write(target / "day74-distribution-scaling-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day74-distribution-scaling-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day74-integration-brief.md", "# Day 74 integration brief\n")
    _write(target / "day74-distribution-scaling-plan.md", "# Day 74 distribution scaling plan\n")
    _write(target / "day74-channel-controls-log.json", json.dumps({"controls": []}, indent=2) + "\n")
    _write(target / "day74-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day74-execution-log.md", "# Day 74 execution log\n")
    _write(target / "day74-delivery-board.md", "\n".join(["# Day 74 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n")
    _write(target / "day74-validation-commands.md", "# Day 74 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n")


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    events: list[dict[str, Any]] = []
    out_dir = evidence_dir if evidence_dir.is_absolute() else root / evidence_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, command in enumerate(_EXECUTION_COMMANDS, start=1):
        result = subprocess.run(shlex.split(command), cwd=root, capture_output=True, text=True)
        event = {"command": command, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        events.append(event)
        _write(out_dir / f"command-{idx:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(out_dir / "day74-execution-summary.json", json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 74 distribution scaling closeout checks")
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
        _write(root / _PAGE_PATH, _DAY74_DEFAULT_PAGE)

    payload = build_day74_distribution_scaling_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = Path(ns.evidence_dir) if ns.evidence_dir else Path("docs/artifacts/day74-distribution-scaling-closeout-pack/evidence")
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
