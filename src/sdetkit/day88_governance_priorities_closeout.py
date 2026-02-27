from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day88-governance-priorities-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY87_SUMMARY_PATH = "docs/artifacts/day87-governance-handoff-closeout-pack/day87-governance-handoff-closeout-summary.json"
_DAY87_BOARD_PATH = "docs/artifacts/day87-governance-handoff-closeout-pack/day87-delivery-board.md"
_PLAN_PATH = ".day88-governance-priorities-plan.json"
_SECTION_HEADER = "# Day 88 — Governance priorities closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 88 matters",
    "## Required inputs (Day 87)",
    "## Day 88 command lane",
    "## Governance priorities contract",
    "## Governance priorities quality checklist",
    "## Day 88 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day88-governance-priorities-closeout --format json --strict",
    "python -m sdetkit day88-governance-priorities-closeout --emit-pack-dir docs/artifacts/day88-governance-priorities-closeout-pack --format json --strict",
    "python -m sdetkit day88-governance-priorities-closeout --execute --evidence-dir docs/artifacts/day88-governance-priorities-closeout-pack/evidence --format json --strict",
    "python scripts/check_day88_governance_priorities_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day88-governance-priorities-closeout --format json --strict",
    "python -m sdetkit day88-governance-priorities-closeout --emit-pack-dir docs/artifacts/day88-governance-priorities-closeout-pack --format json --strict",
    "python scripts/check_day88_governance_priorities_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 88 governance priorities execution and signoff.",
    "The Day 88 lane references Day 87 outcomes, controls, and trust continuity signals.",
    "Every Day 88 section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 88 closeout records governance priorities pack upgrades, storyline outcomes, and Day 89 governance priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes baseline evidence coverage, objection segmentation assumptions, and response SLA targets",
    "- [ ] Every narrative lane row has owner, execution window, KPI threshold, and risk flag",
    "- [ ] CTA links point to narrative docs/templates + runnable command evidence",
    "- [ ] Scorecard captures governance priorities adoption delta, objection deflection delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes narrative brief, evidence plan, template diffs, outcome ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 88 evidence brief committed",
    "- [ ] Day 88 governance priorities plan committed",
    "- [ ] Day 88 narrative template upgrade ledger exported",
    "- [ ] Day 88 storyline outcomes ledger exported",
    "- [ ] Day 89 governance priorities drafted from Day 88 outcomes",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"narrative_channels"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DAY88_DEFAULT_PAGE = """# Day 88 — Governance priorities closeout lane

Day 88 closes with a major upgrade that converts Day 87 governance handoff outcomes into a deterministic governance priorities operating lane.

## Why Day 88 matters

- Converts Day 87 governance handoff outcomes into reusable governance priorities decisions across governance rituals, roadmap reviews, and maintainer escalation paths.
- Protects quality with strict contract coverage, runnable commands, KPI thresholds, and rollback safety.
- Creates a deterministic handoff from Day 88 closeout into Day 89 governance priorities.

## Required inputs (Day 87)

- `docs/artifacts/day87-governance-handoff-closeout-pack/day87-governance-handoff-closeout-summary.json`
- `docs/artifacts/day87-governance-handoff-closeout-pack/day87-delivery-board.md`
- `.day88-governance-priorities-plan.json`

## Day 88 command lane

```bash
python -m sdetkit day88-governance-priorities-closeout --format json --strict
python -m sdetkit day88-governance-priorities-closeout --emit-pack-dir docs/artifacts/day88-governance-priorities-closeout-pack --format json --strict
python -m sdetkit day88-governance-priorities-closeout --execute --evidence-dir docs/artifacts/day88-governance-priorities-closeout-pack/evidence --format json --strict
python scripts/check_day88_governance_priorities_closeout_contract.py
```

## Governance priorities contract

- Single owner + backup reviewer are assigned for Day 88 governance priorities execution and signoff.
- The Day 88 lane references Day 87 outcomes, controls, and trust continuity signals.
- Every Day 88 section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 88 closeout records governance priorities pack upgrades, storyline outcomes, and Day 89 governance priorities.

## Governance priorities quality checklist

- [ ] Includes baseline evidence coverage, objection segmentation assumptions, and response SLA targets
- [ ] Every narrative lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to narrative docs/templates + runnable command evidence
- [ ] Scorecard captures governance priorities adoption delta, objection deflection delta, confidence, and rollback owner
- [ ] Artifact pack includes narrative brief, evidence plan, template diffs, outcome ledger, KPI scorecard, and execution log

## Day 88 delivery board

- [ ] Day 88 evidence brief committed
- [ ] Day 88 governance priorities plan committed
- [ ] Day 88 narrative template upgrade ledger exported
- [ ] Day 88 storyline outcomes ledger exported
- [ ] Day 89 governance priorities drafted from Day 88 outcomes

## Scoring model

Day 88 weights continuity + execution contract + governance artifact readiness for a 100-point activation score.
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


def build_day88_governance_priorities_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read_text(root / "README.md")
    docs_index_text = _read_text(root / "docs/index.md")
    page_text = _read_text(root / _PAGE_PATH)
    top10_text = _read_text(root / _TOP10_PATH)
    day87_summary = root / _DAY87_SUMMARY_PATH
    day87_board = root / _DAY87_BOARD_PATH

    day87_data = _load_json(day87_summary)
    day87_summary_data = (
        day87_data.get("summary", {}) if isinstance(day87_data.get("summary"), dict) else {}
    )
    day87_score = int(day87_summary_data.get("activation_score", 0) or 0)
    day87_strict = bool(day87_summary_data.get("strict_pass", False))
    day87_check_count = (
        len(day87_data.get("checks", [])) if isinstance(day87_data.get("checks"), list) else 0
    )

    board_text = _read_text(day87_board)
    board_count = _checklist_count(board_text)
    board_has_day87 = "Day 87" in board_text

    missing_sections = [section for section in _REQUIRED_SECTIONS if section not in page_text]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]
    missing_contract_lines = [line for line in _REQUIRED_CONTRACT_LINES if line not in page_text]
    missing_quality_lines = [line for line in _REQUIRED_QUALITY_LINES if line not in page_text]
    missing_board_items = [item for item in _REQUIRED_DELIVERY_BOARD_LINES if item not in page_text]

    plan_text = _read_text(root / _PLAN_PATH)
    missing_plan_keys = [key for key in _REQUIRED_DATA_KEYS if key not in plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day88_command",
            "weight": 7,
            "passed": ("day88-governance-priorities-closeout" in readme_text),
            "evidence": "README day88 command lane",
        },
        {
            "check_id": "docs_index_day88_links",
            "weight": 8,
            "passed": (
                "day-88-big-upgrade-report.md" in docs_index_text
                and "integrations-day88-governance-priorities-closeout.md" in docs_index_text
            ),
            "evidence": "day-88-big-upgrade-report.md + integrations-day88-governance-priorities-closeout.md",
        },
        {
            "check_id": "top10_day88_alignment",
            "weight": 5,
            "passed": ("Day 87" in top10_text and "Day 88" in top10_text),
            "evidence": "Day 87 + Day 88 strategy chain",
        },
        {
            "check_id": "day87_summary_present",
            "weight": 10,
            "passed": day87_summary.exists(),
            "evidence": str(day87_summary),
        },
        {
            "check_id": "day87_delivery_board_present",
            "weight": 7,
            "passed": day87_board.exists(),
            "evidence": str(day87_board),
        },
        {
            "check_id": "day87_quality_floor",
            "weight": 13,
            "passed": day87_score >= 85 and day87_strict,
            "evidence": {
                "day87_score": day87_score,
                "strict_pass": day87_strict,
                "day87_checks": day87_check_count,
            },
        },
        {
            "check_id": "day87_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day87,
            "evidence": {"board_items": board_count, "contains_day87": board_has_day87},
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
            "check_id": "evidence_plan_data_present",
            "weight": 10,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day87_summary.exists() or not day87_board.exists():
        critical_failures.append("day87_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day87_score >= 85 and day87_strict:
        wins.append(f"Day 87 continuity baseline is stable with activation score={day87_score}.")
    else:
        misses.append("Day 87 continuity baseline is below the floor (<85) or not strict-pass.")
        handoff_actions.append(
            "Re-run Day 87 closeout command and raise baseline quality above 85 with strict pass before Day 88 lock."
        )

    if board_count >= 5 and board_has_day87:
        wins.append(
            f"Day 87 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 87 delivery board integrity is incomplete (needs >=5 items and Day 87 anchors)."
        )
        handoff_actions.append("Repair Day 87 delivery board entries to include Day 87 anchors.")

    if not missing_plan_keys:
        wins.append("Day 88 governance priorities dataset is available for governance execution.")
    else:
        misses.append("Day 88 governance priorities dataset is missing required keys.")
        handoff_actions.append(
            "Update .day88-governance-priorities-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 88 governance priorities closeout lane is fully complete and ready for Day 89 governance planning."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day88-governance-priorities-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day87_summary": str(day87_summary.relative_to(root))
            if day87_summary.exists()
            else str(day87_summary),
            "day87_delivery_board": str(day87_board.relative_to(root))
            if day87_board.exists()
            else str(day87_board),
            "governance_priorities_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "day87_activation_score": day87_score,
            "day87_checks": day87_check_count,
            "day87_delivery_board_items": board_count,
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
        "Day 88 governance priorities closeout summary",
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
        target / "day88-governance-priorities-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "day88-governance-priorities-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day88-evidence-brief.md", "# Day 88 governance priorities brief\n")
    _write(target / "day88-governance-priorities-plan.md", "# Day 88 governance priorities plan\n")
    _write(
        target / "day88-narrative-template-upgrade-ledger.json",
        json.dumps({"upgrades": []}, indent=2) + "\n",
    )
    _write(
        target / "day88-storyline-outcomes-ledger.json",
        json.dumps({"outcomes": []}, indent=2) + "\n",
    )
    _write(target / "day88-narrative-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day88-execution-log.md", "# Day 88 execution log\n")
    _write(
        target / "day88-delivery-board.md",
        "\n".join(["# Day 88 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day88-validation-commands.md",
        "# Day 88 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    events: list[dict[str, Any]] = []
    out_dir = evidence_dir if evidence_dir.is_absolute() else root / evidence_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, command in enumerate(_EXECUTION_COMMANDS, start=1):
        result = subprocess.run(shlex.split(command), cwd=root, capture_output=True, text=True)
        event = {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        events.append(event)
        _write(out_dir / f"command-{idx:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        out_dir / "day88-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 88 governance priorities closeout checks")
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
        _write(root / _PAGE_PATH, _DAY88_DEFAULT_PAGE)

    payload = build_day88_governance_priorities_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day88-governance-priorities-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
