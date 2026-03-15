from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-continuous-upgrade-cycle9-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_PREV_CYCLE_SUMMARY_PATH = "docs/artifacts/continuous-upgrade-cycle8-closeout-pack/cycle8-continuous-upgrade-cycle8-closeout-summary.json"
_PREV_CYCLE_BOARD_PATH = (
    "docs/artifacts/continuous-upgrade-cycle8-closeout-pack/cycle8-delivery-board.md"
)
_PLAN_PATH = "docs/roadmap/plans/continuous-upgrade-cycle9-plan.json"
_SECTION_HEADER = "# Cycle 9 \u2014 Continuous upgrade closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Cycle 9 matters",
    "## Required inputs (Cycle 8)",
    "## Cycle 9 command lane",
    "## Continuous upgrade contract",
    "## Continuous upgrade quality checklist",
    "## Cycle 9 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit continuous-upgrade-cycle9-closeout --format json --strict",
    "python -m sdetkit continuous-upgrade-cycle9-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle9-closeout-pack --format json --strict",
    "python -m sdetkit continuous-upgrade-cycle9-closeout --execute --evidence-dir docs/artifacts/continuous-upgrade-cycle9-closeout-pack/evidence --format json --strict",
    "python scripts/check_continuous_upgrade_cycle9_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit continuous-upgrade-cycle9-closeout --format json --strict",
    "python -m sdetkit continuous-upgrade-cycle9-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle9-closeout-pack --format json --strict",
    "python scripts/check_continuous_upgrade_cycle9_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Cycle 9 continuous upgrade execution and signoff.",
    "The Cycle 9 lane references Cycle 8 outcomes, controls, and trust continuity signals.",
    "Every Cycle 9 section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Cycle 9 closeout records continuous upgrade outputs, report publication status, and backlog inputs.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes baseline evidence coverage, objection segmentation assumptions, and response SLA targets",
    "- [ ] Every upgrade lane row has owner, execution window, KPI threshold, and risk flag",
    "- [ ] CTA links point to upgrade docs/templates + runnable command evidence",
    "- [ ] Scorecard captures continuous upgrade adoption delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes upgrade brief, evidence plan, template diffs, outcome ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Cycle 9 evidence brief committed",
    "- [ ] Cycle 9 continuous upgrade plan committed",
    "- [ ] Cycle 9 upgrade template upgrade ledger exported",
    "- [ ] Cycle 9 storyline outcomes ledger exported",
    "- [ ] Next-impact roadmap draft captured from Cycle 9 outcomes",
]
_REQUIRED_DATA_KEYS = [
    "plan_id",
    "contributors",
    "upgrade_channels",
    "baseline",
    "target",
    "owner",
    "rollback_owner",
    "confidence_floor",
    "cadence_days",
]

_CYCLE9_DEFAULT_PAGE = """# Cycle 9 \u2014 Continuous upgrade closeout lane

Cycle 9 closes with a major upgrade that converts Cycle 8 governance scale outcomes into a deterministic phase-3 wrap and publication operating lane.

## Why Cycle 9 matters

- Converts Cycle 8 governance scale outcomes into reusable publication decisions across release recap, roadmap governance, and maintainer escalation paths.
- Protects quality with strict contract coverage, runnable commands, KPI thresholds, and rollback safety.
- Creates a deterministic handoff from Cycle 9 closeout into the continuous-upgrade backlog.

## Required inputs (Cycle 8)

- `docs/artifacts/continuous-upgrade-cycle8-closeout-pack/cycle8-continuous-upgrade-cycle8-closeout-summary.json`
- `docs/artifacts/continuous-upgrade-cycle8-closeout-pack/cycle8-delivery-board.md`
- `docs/roadmap/plans/continuous-upgrade-cycle9-plan.json`

## Cycle 9 command lane

```bash
python -m sdetkit continuous-upgrade-cycle9-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle9-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle9-closeout-pack --format json --strict
python -m sdetkit continuous-upgrade-cycle9-closeout --execute --evidence-dir docs/artifacts/continuous-upgrade-cycle9-closeout-pack/evidence --format json --strict
python scripts/check_continuous_upgrade_cycle9_closeout_contract.py
```

## Continuous upgrade contract

- Single owner + backup reviewer are assigned for Cycle 9 continuous upgrade execution and signoff.
- The Cycle 9 lane references Cycle 8 outcomes, controls, and trust continuity signals.
- Every Cycle 9 section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Cycle 9 closeout records continuous upgrade outputs, report publication status, and backlog inputs.

## Continuous upgrade quality checklist

- [ ] Includes baseline evidence coverage, objection segmentation assumptions, and response SLA targets
- [ ] Every upgrade lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to upgrade docs/templates + runnable command evidence
- [ ] Scorecard captures continuous upgrade adoption delta, confidence, and rollback owner
- [ ] Artifact pack includes upgrade brief, evidence plan, template diffs, outcome ledger, KPI scorecard, and execution log

## Cycle 9 delivery board

- [ ] Cycle 9 evidence brief committed
- [ ] Cycle 9 continuous upgrade plan committed
- [ ] Cycle 9 upgrade template upgrade ledger exported
- [ ] Cycle 9 storyline outcomes ledger exported
- [ ] Next-impact roadmap draft captured from Cycle 9 outcomes

## Scoring model

Cycle 9 weights continuity + execution contract + governance artifact readiness for a 100-point activation score.
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


def _validate_plan_contract(
    plan_data: dict[str, Any],
) -> tuple[list[str], list[str], list[str], list[str]]:
    missing_keys = [key for key in _REQUIRED_DATA_KEYS if key not in plan_data]

    trajectory_issues: list[str] = []
    baseline_raw = plan_data.get("baseline")
    baseline = baseline_raw if isinstance(baseline_raw, dict) else {}
    target_raw = plan_data.get("target")
    target = target_raw if isinstance(target_raw, dict) else {}

    if not baseline:
        trajectory_issues.append("baseline: missing or not an object")
    if not target:
        trajectory_issues.append("target: missing or not an object")

    for metric, baseline_value in baseline.items():
        target_value = target.get(metric)
        if isinstance(baseline_value, (int, float)):
            if not isinstance(target_value, (int, float)):
                trajectory_issues.append(f"{metric}: missing numeric target")
            elif target_value < baseline_value:
                trajectory_issues.append(
                    f"{metric}: target {target_value} below baseline {baseline_value}"
                )

    owner_issues: list[str] = []
    for owner_field in ("owner", "rollback_owner"):
        value = plan_data.get(owner_field)
        if not isinstance(value, str) or not value.strip():
            owner_issues.append(f"{owner_field}: missing owner assignment")

    hygiene_issues: list[str] = []
    contributors = plan_data.get("contributors")
    if not isinstance(contributors, list) or not contributors:
        hygiene_issues.append("contributors: must contain at least one contributor")
    elif not all(isinstance(item, str) and item.strip() for item in contributors):
        hygiene_issues.append("contributors: every contributor must be a non-empty string")

    channels = plan_data.get("upgrade_channels")
    if not isinstance(channels, list) or not channels:
        hygiene_issues.append("upgrade_channels: must contain at least one lane")
    elif not all(isinstance(item, str) and item.strip() for item in channels):
        hygiene_issues.append("upgrade_channels: every channel must be a non-empty string")

    confidence_floor = plan_data.get("confidence_floor")
    if not isinstance(confidence_floor, (int, float)) or not (0 <= confidence_floor <= 1):
        hygiene_issues.append("confidence_floor: must be a number between 0 and 1")

    cadence_days = plan_data.get("cadence_days")
    if not isinstance(cadence_days, int) or cadence_days <= 0:
        hygiene_issues.append("cadence_days: must be a positive integer")

    return missing_keys, trajectory_issues, owner_issues, hygiene_issues


def build_continuous_upgrade_cycle9_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read_text(root / "README.md")
    docs_index_text = _read_text(root / "docs/index.md")
    page_text = _read_text(root / _PAGE_PATH)
    top10_text = _read_text(root / _TOP10_PATH)
    cycle8_summary = root / _PREV_CYCLE_SUMMARY_PATH
    cycle8_board = root / _PREV_CYCLE_BOARD_PATH

    cycle8_data = _load_json(cycle8_summary)
    cycle8_summary_data = (
        cycle8_data.get("summary", {}) if isinstance(cycle8_data.get("summary"), dict) else {}
    )
    cycle8_score = int(cycle8_summary_data.get("activation_score", 0) or 0)
    cycle8_strict = bool(cycle8_summary_data.get("strict_pass", False))
    cycle8_check_count = (
        len(cycle8_data.get("checks", [])) if isinstance(cycle8_data.get("checks"), list) else 0
    )

    board_text = _read_text(cycle8_board)
    board_count = _checklist_count(board_text)
    board_has_cycle8 = "Cycle 8" in board_text

    missing_sections = [section for section in _REQUIRED_SECTIONS if section not in page_text]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]
    missing_contract_lines = [line for line in _REQUIRED_CONTRACT_LINES if line not in page_text]
    missing_quality_lines = [line for line in _REQUIRED_QUALITY_LINES if line not in page_text]
    missing_board_items = [item for item in _REQUIRED_DELIVERY_BOARD_LINES if item not in page_text]

    plan_data = _load_json(root / _PLAN_PATH)
    missing_plan_keys, plan_trajectory_issues, plan_owner_issues, plan_hygiene_issues = (
        _validate_plan_contract(plan_data)
    )

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_cycle9_command",
            "weight": 5,
            "passed": ("continuous-upgrade-cycle9-closeout" in readme_text),
            "evidence": "README cycle9 command lane",
        },
        {
            "check_id": "docs_index_cycle9_links",
            "weight": 8,
            "passed": (
                "continuous-upgrade-cycle9-big-upgrade-report.md" in docs_index_text
                and "integrations-continuous-upgrade-cycle9-closeout.md" in docs_index_text
            ),
            "evidence": "continuous-upgrade-cycle9-big-upgrade-report.md + integrations-continuous-upgrade-cycle9-closeout.md",
        },
        {
            "check_id": "top10_cycle9_align",
            "weight": 5,
            "passed": (
                ("Cycle 8" in top10_text or "Day 97" in top10_text) and "Cycle 9" in top10_text
            ),
            "evidence": "Cycle 8/Day 97 + Cycle 9 strategy chain",
        },
        {
            "check_id": "cycle8_summary_present",
            "weight": 10,
            "passed": cycle8_summary.exists(),
            "evidence": str(cycle8_summary),
        },
        {
            "check_id": "cycle8_delivery_board_present",
            "weight": 7,
            "passed": cycle8_board.exists(),
            "evidence": str(cycle8_board),
        },
        {
            "check_id": "cycle8_quality_floor",
            "weight": 13,
            "passed": cycle8_score >= 85 and cycle8_strict,
            "evidence": {
                "cycle8_score": cycle8_score,
                "strict_pass": cycle8_strict,
                "cycle8_checks": cycle8_check_count,
            },
        },
        {
            "check_id": "cycle8_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_cycle8,
            "evidence": {"board_items": board_count, "contains_cycle8": board_has_cycle8},
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
            "weight": 4,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _PLAN_PATH,
        },
        {
            "check_id": "evidence_plan_targets_non_regressive",
            "weight": 4,
            "passed": not plan_trajectory_issues,
            "evidence": plan_trajectory_issues or "target metrics are non-regressive",
        },
        {
            "check_id": "evidence_plan_owner_coverage",
            "weight": 2,
            "passed": not plan_owner_issues,
            "evidence": plan_owner_issues or "owner + rollback owner assigned",
        },
        {
            "check_id": "evidence_plan_hygiene",
            "weight": 2,
            "passed": not plan_hygiene_issues,
            "evidence": plan_hygiene_issues or "contributors/channels/confidence/cadence validated",
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not cycle8_summary.exists() or not cycle8_board.exists():
        # sdetkit: allow-security SEC_HIGH_ENTROPY_STRING
        critical_failures.append("cycle8_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if cycle8_score >= 85 and cycle8_strict:
        wins.append(f"Cycle 9 continuity baseline is stable with activation score={cycle8_score}.")
    else:
        misses.append("Cycle 9 continuity baseline is below the floor (<85) or not strict-pass.")
        handoff_actions.append(
            "Re-run Cycle 8 closeout command and raise baseline quality above 85 with strict pass before Cycle 9 lock."
        )

    if board_count >= 5 and board_has_cycle8:
        wins.append(
            f"Cycle 9 predecessor delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Cycle 9 predecessor delivery board integrity is incomplete (needs >=5 items and Cycle 8 anchors)."
        )
        handoff_actions.append(
            "Repair predecessor delivery board entries to include Cycle 8 anchors."
        )

    if not missing_plan_keys:
        wins.append("Cycle 9 continuous upgrade dataset is available for governance execution.")
    else:
        misses.append("Cycle 9 continuous upgrade dataset is missing required keys.")
        handoff_actions.append(
            "Update docs/roadmap/plans/continuous-upgrade-cycle9-plan.json to restore required keys."
        )

    if not plan_trajectory_issues:
        wins.append("Cycle 9 target metrics are non-regressive against baseline metrics.")
    else:
        misses.append("Cycle 9 target metrics regress against baseline metrics.")
        handoff_actions.append(
            "Adjust docs/roadmap/plans/continuous-upgrade-cycle9-plan.json target metrics so each numeric target is >= baseline."
        )

    if not plan_owner_issues:
        wins.append("Cycle 9 owner coverage includes both execution and rollback ownership.")
    else:
        misses.append("Cycle 9 owner coverage is missing execution and/or rollback ownership.")
        handoff_actions.append(
            "Assign both owner and rollback_owner in docs/roadmap/plans/continuous-upgrade-cycle9-plan.json."
        )

    if not plan_hygiene_issues:
        wins.append(
            "Cycle 9 plan hygiene checks passed for contributors/channels/confidence/cadence."
        )
    else:
        misses.append(
            "Cycle 9 plan hygiene checks failed for contributors/channels/confidence/cadence."
        )
        handoff_actions.append(
            "Fix contributors/upgrade_channels list shapes and confidence_floor/cadence_days bounds in docs/roadmap/plans/continuous-upgrade-cycle9-plan.json."
        )

    if not failed and not critical_failures:
        wins.append(
            "Cycle 9 continuous upgrade closeout lane is fully complete and ready for continuous-upgrade backlog execution."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "continuous-upgrade-cycle9-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "cycle8_summary": str(cycle8_summary.relative_to(root))
            if cycle8_summary.exists()
            else str(cycle8_summary),
            "cycle8_delivery_board": str(cycle8_board.relative_to(root))
            if cycle8_board.exists()
            else str(cycle8_board),
            "continuous_upgrade_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "cycle8_activation_score": cycle8_score,
            "cycle8_checks": cycle8_check_count,
            "cycle8_delivery_board_items": board_count,
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
        "Cycle 9 continuous upgrade closeout summary",
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
        target / "continuous-upgrade-cycle9-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "continuous-upgrade-cycle9-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "cycle9-evidence-brief.md", "# Cycle 9 continuous upgrade brief\n")
    _write(target / "cycle9-continuous-upgrade-plan.md", "# Cycle 9 continuous upgrade plan\n")
    _write(
        target / "cycle9-upgrade-template-upgrade-ledger.json",
        json.dumps({"upgrades": []}, indent=2) + "\n",
    )
    _write(
        target / "cycle9-storyline-outcomes-ledger.json",
        json.dumps({"outcomes": []}, indent=2) + "\n",
    )
    _write(target / "cycle9-upgrade-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "cycle9-execution-log.md", "# Cycle 9 execution log\n")
    _write(
        target / "cycle9-delivery-board.md",
        "\n".join(["# Cycle 9 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "cycle9-validation-commands.md",
        "# Cycle 9 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> dict[str, Any]:
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
    failed_commands = [event for event in events if int(event["returncode"]) != 0]
    summary = {
        "total_commands": len(events),
        "failed_commands": len(failed_commands),
        "strict_pass": not failed_commands,
        "commands": events,
    }
    _write(
        out_dir / "cycle9-execution-summary.json",
        json.dumps(summary, indent=2) + "\n",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cycle 9 continuous upgrade closeout checks")
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
        _write(root / _PAGE_PATH, _CYCLE9_DEFAULT_PAGE)

    payload = build_continuous_upgrade_cycle9_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/continuous-upgrade-cycle9-closeout-pack/evidence")
        )
        execution_summary = _execute_commands(root, evidence_dir)
        payload["execution"] = execution_summary

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    strict_failed = not payload["summary"]["strict_pass"]
    if ns.execute:
        strict_failed = strict_failed or not bool(
            payload.get("execution", {}).get("strict_pass", True)
        )
    return 1 if ns.strict and strict_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
