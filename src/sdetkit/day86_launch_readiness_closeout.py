from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day86-launch-readiness-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY85_SUMMARY_PATH = "docs/artifacts/day85-release-prioritization-closeout-pack/day85-release-prioritization-closeout-summary.json"
_DAY85_BOARD_PATH = "docs/artifacts/day85-release-prioritization-closeout-pack/day85-delivery-board.md"
_PLAN_PATH = ".day86-launch-readiness-plan.json"
_SECTION_HEADER = "# Day 86 — Launch readiness closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 86 matters",
    "## Required inputs (Day 85)",
    "## Day 86 command lane",
    "## Launch readiness contract",
    "## Launch readiness quality checklist",
    "## Day 86 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day86-launch-readiness-closeout --format json --strict",
    "python -m sdetkit day86-launch-readiness-closeout --emit-pack-dir docs/artifacts/day86-launch-readiness-closeout-pack --format json --strict",
    "python -m sdetkit day86-launch-readiness-closeout --execute --evidence-dir docs/artifacts/day86-launch-readiness-closeout-pack/evidence --format json --strict",
    "python scripts/check_day86_launch_readiness_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day86-launch-readiness-closeout --format json --strict",
    "python -m sdetkit day86-launch-readiness-closeout --emit-pack-dir docs/artifacts/day86-launch-readiness-closeout-pack --format json --strict",
    "python scripts/check_day86_launch_readiness_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 86 launch readiness execution and signoff.",
    "The Day 86 lane references Day 85 outcomes, controls, and trust continuity signals.",
    "Every Day 86 section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 86 closeout records launch readiness pack upgrades, storyline outcomes, and Day 87 launch priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes baseline evidence coverage, objection segmentation assumptions, and response SLA targets",
    "- [ ] Every narrative lane row has owner, execution window, KPI threshold, and risk flag",
    "- [ ] CTA links point to narrative docs/templates + runnable command evidence",
    "- [ ] Scorecard captures launch readiness adoption delta, objection deflection delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes narrative brief, evidence plan, template diffs, outcome ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 86 evidence brief committed",
    "- [ ] Day 86 launch readiness plan committed",
    "- [ ] Day 86 narrative template upgrade ledger exported",
    "- [ ] Day 86 storyline outcomes ledger exported",
    "- [ ] Day 87 launch priorities drafted from Day 86 outcomes",
]
_REQUIRED_DATA_KEYS = ['"plan_id"', '"contributors"', '"narrative_channels"', '"baseline"', '"target"', '"owner"']

_DAY86_DEFAULT_PAGE = """# Day 86 — Launch readiness closeout lane

Day 86 closes with a major upgrade that converts Day 85 release prioritization outcomes into a deterministic launch readiness operating lane.

## Why Day 86 matters

- Converts Day 85 release prioritization outcomes into reusable launch readiness decisions across launch briefs, release notes, and escalation playbooks.
- Protects quality with strict contract coverage, runnable commands, KPI thresholds, and rollback safety.
- Creates a deterministic handoff from Day 86 closeout into Day 87 launch priorities.

## Required inputs (Day 85)

- `docs/artifacts/day85-release-prioritization-closeout-pack/day85-release-prioritization-closeout-summary.json`
- `docs/artifacts/day85-release-prioritization-closeout-pack/day85-delivery-board.md`
- `.day86-launch-readiness-plan.json`

## Day 86 command lane

```bash
python -m sdetkit day86-launch-readiness-closeout --format json --strict
python -m sdetkit day86-launch-readiness-closeout --emit-pack-dir docs/artifacts/day86-launch-readiness-closeout-pack --format json --strict
python -m sdetkit day86-launch-readiness-closeout --execute --evidence-dir docs/artifacts/day86-launch-readiness-closeout-pack/evidence --format json --strict
python scripts/check_day86_launch_readiness_closeout_contract.py
```

## Launch readiness contract

- Single owner + backup reviewer are assigned for Day 86 launch readiness execution and signoff.
- The Day 86 lane references Day 85 outcomes, controls, and trust continuity signals.
- Every Day 86 section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 86 closeout records launch readiness pack upgrades, storyline outcomes, and Day 87 launch priorities.

## Launch readiness quality checklist

- [ ] Includes baseline evidence coverage, objection segmentation assumptions, and response SLA targets
- [ ] Every narrative lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to narrative docs/templates + runnable command evidence
- [ ] Scorecard captures launch readiness adoption delta, objection deflection delta, confidence, and rollback owner
- [ ] Artifact pack includes narrative brief, evidence plan, template diffs, outcome ledger, KPI scorecard, and execution log

## Day 86 delivery board

- [ ] Day 86 evidence brief committed
- [ ] Day 86 launch readiness plan committed
- [ ] Day 86 narrative template upgrade ledger exported
- [ ] Day 86 storyline outcomes ledger exported
- [ ] Day 87 launch priorities drafted from Day 86 outcomes

## Scoring model

Day 86 weights continuity + execution contract + launch artifact readiness for a 100-point activation score.
"""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _checklist_count(markdown: str) -> int:
    return sum(1 for line in markdown.splitlines() if line.strip().startswith("- ["))


def build_day86_launch_readiness_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read_text(root / "README.md")
    docs_index_text = _read_text(root / "docs/index.md")
    page_text = _read_text(root / _PAGE_PATH)
    top10_text = _read_text(root / _TOP10_PATH)
    day85_summary = root / _DAY85_SUMMARY_PATH
    day85_board = root / _DAY85_BOARD_PATH

    day85_data = _load_json(day85_summary)
    day85_summary_data = day85_data.get("summary", {}) if isinstance(day85_data.get("summary"), dict) else {}
    day85_score = int(day85_summary_data.get("activation_score", 0) or 0)
    day85_strict = bool(day85_summary_data.get("strict_pass", False))
    day85_check_count = len(day85_data.get("checks", [])) if isinstance(day85_data.get("checks"), list) else 0

    board_text = _read_text(day85_board)
    board_count = _checklist_count(board_text)
    board_has_day85 = "Day 85" in board_text

    missing_sections = [section for section in _REQUIRED_SECTIONS if section not in page_text]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]
    missing_contract_lines = [line for line in _REQUIRED_CONTRACT_LINES if line not in page_text]
    missing_quality_lines = [line for line in _REQUIRED_QUALITY_LINES if line not in page_text]
    missing_board_items = [item for item in _REQUIRED_DELIVERY_BOARD_LINES if item not in page_text]

    plan_text = _read_text(root / _PLAN_PATH)
    missing_plan_keys = [key for key in _REQUIRED_DATA_KEYS if key not in plan_text]

    checks: list[dict[str, Any]] = [
        {"check_id": "readme_day86_command", "weight": 7, "passed": ("day86-launch-readiness-closeout" in readme_text), "evidence": "README day86 command lane"},
        {
            "check_id": "docs_index_day86_links",
            "weight": 8,
            "passed": ("day-86-big-upgrade-report.md" in docs_index_text and "integrations-day86-launch-readiness-closeout.md" in docs_index_text),
            "evidence": "day-86-big-upgrade-report.md + integrations-day86-launch-readiness-closeout.md",
        },
        {"check_id": "top10_day86_alignment", "weight": 5, "passed": ("Day 85" in top10_text and "Day 86" in top10_text), "evidence": "Day 85 + Day 86 strategy chain"},
        {"check_id": "day85_summary_present", "weight": 10, "passed": day85_summary.exists(), "evidence": str(day85_summary)},
        {"check_id": "day85_delivery_board_present", "weight": 7, "passed": day85_board.exists(), "evidence": str(day85_board)},
        {
            "check_id": "day85_quality_floor",
            "weight": 13,
            "passed": day85_score >= 85 and day85_strict,
            "evidence": {"day85_score": day85_score, "strict_pass": day85_strict, "day85_checks": day85_check_count},
        },
        {
            "check_id": "day85_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day85,
            "evidence": {"board_items": board_count, "contains_day85": board_has_day85},
        },
        {"check_id": "page_header", "weight": 7, "passed": _SECTION_HEADER in page_text, "evidence": _SECTION_HEADER},
        {"check_id": "required_sections", "weight": 8, "passed": not missing_sections, "evidence": missing_sections or "all sections present"},
        {"check_id": "required_commands", "weight": 5, "passed": not missing_commands, "evidence": missing_commands or "all commands present"},
        {"check_id": "contract_lock", "weight": 5, "passed": not missing_contract_lines, "evidence": missing_contract_lines or "contract locked"},
        {"check_id": "quality_checklist_lock", "weight": 5, "passed": not missing_quality_lines, "evidence": missing_quality_lines or "quality checklist locked"},
        {"check_id": "delivery_board_lock", "weight": 5, "passed": not missing_board_items, "evidence": missing_board_items or "delivery board locked"},
        {"check_id": "evidence_plan_data_present", "weight": 10, "passed": not missing_plan_keys, "evidence": missing_plan_keys or _PLAN_PATH},
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day85_summary.exists() or not day85_board.exists():
        critical_failures.append("day85_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day85_score >= 85 and day85_strict:
        wins.append(f"Day 85 continuity baseline is stable with activation score={day85_score}.")
    else:
        misses.append("Day 85 continuity baseline is below the floor (<85) or not strict-pass.")
        handoff_actions.append("Re-run Day 85 closeout command and raise baseline quality above 85 with strict pass before Day 86 lock.")

    if board_count >= 5 and board_has_day85:
        wins.append(f"Day 85 delivery board integrity validated with {board_count} checklist items.")
    else:
        misses.append("Day 85 delivery board integrity is incomplete (needs >=5 items and Day 85 anchors).")
        handoff_actions.append("Repair Day 85 delivery board entries to include Day 85 anchors.")

    if not missing_plan_keys:
        wins.append("Day 86 launch readiness dataset is available for launch execution.")
    else:
        misses.append("Day 86 launch readiness dataset is missing required keys.")
        handoff_actions.append("Update .day86-launch-readiness-plan.json to restore required keys.")

    if not failed and not critical_failures:
        wins.append("Day 86 launch readiness closeout lane is fully complete and ready for Day 87 launch planning.")

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day86-launch-readiness-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day85_summary": str(day85_summary.relative_to(root)) if day85_summary.exists() else str(day85_summary),
            "day85_delivery_board": str(day85_board.relative_to(root)) if day85_board.exists() else str(day85_board),
            "launch_readiness_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {"day85_activation_score": day85_score, "day85_checks": day85_check_count, "day85_delivery_board_items": board_count},
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
        "Day 86 launch readiness closeout summary",
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
    _write(target / "day86-launch-readiness-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day86-launch-readiness-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day86-evidence-brief.md", "# Day 86 launch readiness brief\n")
    _write(target / "day86-launch-readiness-plan.md", "# Day 86 launch readiness plan\n")
    _write(target / "day86-narrative-template-upgrade-ledger.json", json.dumps({"upgrades": []}, indent=2) + "\n")
    _write(target / "day86-storyline-outcomes-ledger.json", json.dumps({"outcomes": []}, indent=2) + "\n")
    _write(target / "day86-narrative-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day86-execution-log.md", "# Day 86 execution log\n")
    _write(target / "day86-delivery-board.md", "\n".join(["# Day 86 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n")
    _write(target / "day86-validation-commands.md", "# Day 86 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n")


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    events: list[dict[str, Any]] = []
    out_dir = evidence_dir if evidence_dir.is_absolute() else root / evidence_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, command in enumerate(_EXECUTION_COMMANDS, start=1):
        result = subprocess.run(shlex.split(command), cwd=root, capture_output=True, text=True)
        event = {"command": command, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        events.append(event)
        _write(out_dir / f"command-{idx:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(out_dir / "day86-execution-summary.json", json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 86 launch readiness closeout checks")
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
        _write(root / _PAGE_PATH, _DAY86_DEFAULT_PAGE)

    payload = build_day86_launch_readiness_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = Path(ns.evidence_dir) if ns.evidence_dir else Path("docs/artifacts/day86-launch-readiness-closeout-pack/evidence")
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
