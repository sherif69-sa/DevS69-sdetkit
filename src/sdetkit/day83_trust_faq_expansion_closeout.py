from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day83-trust-faq-expansion-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY82_SUMMARY_PATH = "docs/artifacts/day82-integration-feedback-closeout-pack/day82-integration-feedback-closeout-summary.json"
_DAY82_BOARD_PATH = (
    "docs/artifacts/day82-integration-feedback-closeout-pack/day82-delivery-board.md"
)
_PLAN_PATH = ".day83-trust-faq-expansion-plan.json"
_SECTION_HEADER = "# Day 83 \u2014 Trust FAQ expansion loop closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 83 matters",
    "## Required inputs (Day 82)",
    "## Day 83 command lane",
    "## Trust FAQ expansion contract",
    "## Trust FAQ expansion quality checklist",
    "## Day 83 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day83-trust-faq-expansion-closeout --format json --strict",
    "python -m sdetkit day83-trust-faq-expansion-closeout --emit-pack-dir docs/artifacts/day83-trust-faq-expansion-closeout-pack --format json --strict",
    "python -m sdetkit day83-trust-faq-expansion-closeout --execute --evidence-dir docs/artifacts/day83-trust-faq-expansion-closeout-pack/evidence --format json --strict",
    "python scripts/check_day83_trust_faq_expansion_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day83-trust-faq-expansion-closeout --format json --strict",
    "python -m sdetkit day83-trust-faq-expansion-closeout --emit-pack-dir docs/artifacts/day83-trust-faq-expansion-closeout-pack --format json --strict",
    "python scripts/check_day83_trust_faq_expansion_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 83 trust FAQ expansion execution and signoff.",
    "The Day 83 lane references Day 82 outcomes, controls, and campaign continuity signals.",
    "Every Day 83 section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 83 closeout records trust FAQ content upgrades, escalation outcomes, and Day 84 evidence narrative priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes baseline trust FAQ coverage, objection segmentation assumptions, and response SLA targets",
    "- [ ] Every trust lane row has owner, execution window, KPI threshold, and risk flag",
    "- [ ] CTA links point to trust docs/templates + runnable command evidence",
    "- [ ] Scorecard captures trust FAQ adoption delta, objection deflection delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes trust brief, FAQ expansion plan, template diffs, escalation ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 83 trust FAQ brief committed",
    "- [ ] Day 83 trust FAQ expansion plan committed",
    "- [ ] Day 83 trust template upgrade ledger exported",
    "- [ ] Day 83 escalation outcomes ledger exported",
    "- [ ] Day 84 evidence narrative priorities drafted from Day 83 outcomes",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"objection_channels"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DAY83_DEFAULT_PAGE = """# Day 83 \u2014 Trust FAQ expansion loop closeout lane

Day 83 closes with a major upgrade that folds Day 82 integration feedback outcomes into trust FAQ coverage upgrades and escalation-readiness execution.

## Why Day 83 matters

- Turns Day 82 integration feedback outcomes into deterministic trust FAQ expansion loops across docs, templates, and support operations.
- Protects quality with strict contract coverage, runnable commands, KPI thresholds, and rollback safety.
- Creates a deterministic handoff from Day 83 closeout into Day 84 evidence narrative priorities.

## Required inputs (Day 82)

- `docs/artifacts/day82-integration-feedback-closeout-pack/day82-integration-feedback-closeout-summary.json`
- `docs/artifacts/day82-integration-feedback-closeout-pack/day82-delivery-board.md`
- `.day83-trust-faq-expansion-plan.json`

## Day 83 command lane

```bash
python -m sdetkit day83-trust-faq-expansion-closeout --format json --strict
python -m sdetkit day83-trust-faq-expansion-closeout --emit-pack-dir docs/artifacts/day83-trust-faq-expansion-closeout-pack --format json --strict
python -m sdetkit day83-trust-faq-expansion-closeout --execute --evidence-dir docs/artifacts/day83-trust-faq-expansion-closeout-pack/evidence --format json --strict
python scripts/check_day83_trust_faq_expansion_closeout_contract.py
```

## Trust FAQ expansion contract

- Single owner + backup reviewer are assigned for Day 83 trust FAQ expansion execution and signoff.
- The Day 83 lane references Day 82 outcomes, controls, and campaign continuity signals.
- Every Day 83 section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 83 closeout records trust FAQ content upgrades, escalation outcomes, and Day 84 evidence narrative priorities.

## Trust FAQ expansion quality checklist

- [ ] Includes baseline trust FAQ coverage, objection segmentation assumptions, and response SLA targets
- [ ] Every trust lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to trust docs/templates + runnable command evidence
- [ ] Scorecard captures trust FAQ adoption delta, objection deflection delta, confidence, and rollback owner
- [ ] Artifact pack includes trust brief, FAQ expansion plan, template diffs, escalation ledger, KPI scorecard, and execution log

## Day 83 delivery board

- [ ] Day 83 trust FAQ brief committed
- [ ] Day 83 trust FAQ expansion plan committed
- [ ] Day 83 trust template upgrade ledger exported
- [ ] Day 83 escalation outcomes ledger exported
- [ ] Day 84 evidence narrative priorities drafted from Day 83 outcomes

## Scoring model

Day 83 weighted score (0-100):

- Contract + command lane integrity (35)
- Day 82 continuity baseline quality (35)
- Feedback evidence data + delivery board completeness (30)
"""


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _checklist_count(markdown: str) -> int:
    return sum(1 for line in markdown.splitlines() if line.strip().startswith("- ["))


def build_day83_trust_faq_expansion_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read_text(root / "README.md")
    docs_index_text = _read_text(root / "docs/index.md")
    page_text = _read_text(root / _PAGE_PATH)
    top10_text = _read_text(root / _TOP10_PATH)
    day82_summary = root / _DAY82_SUMMARY_PATH
    day82_board = root / _DAY82_BOARD_PATH

    day82_data = _load_json(day82_summary)
    day82_summary_data = (
        day82_data.get("summary", {}) if isinstance(day82_data.get("summary"), dict) else {}
    )
    day82_score = int(day82_summary_data.get("activation_score", 0) or 0)
    day82_strict = bool(day82_summary_data.get("strict_pass", False))
    day82_check_count = (
        len(day82_data.get("checks", [])) if isinstance(day82_data.get("checks"), list) else 0
    )

    board_text = _read_text(day82_board)
    board_count = _checklist_count(board_text)
    board_has_day82 = "Day 82" in board_text

    missing_sections = [section for section in _REQUIRED_SECTIONS if section not in page_text]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]
    missing_contract_lines = [line for line in _REQUIRED_CONTRACT_LINES if line not in page_text]
    missing_quality_lines = [line for line in _REQUIRED_QUALITY_LINES if line not in page_text]
    missing_board_items = [item for item in _REQUIRED_DELIVERY_BOARD_LINES if item not in page_text]

    plan_text = _read_text(root / _PLAN_PATH)
    missing_plan_keys = [key for key in _REQUIRED_DATA_KEYS if key not in plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day83_command",
            "weight": 7,
            "passed": ("day83-trust-faq-expansion-closeout" in readme_text),
            "evidence": "README day83 command lane",
        },
        {
            "check_id": "docs_index_day83_links",
            "weight": 8,
            "passed": (
                "day-83-big-upgrade-report.md" in docs_index_text
                and "integrations-day83-trust-faq-expansion-closeout.md" in docs_index_text
            ),
            "evidence": "day-83-big-upgrade-report.md + integrations-day83-trust-faq-expansion-closeout.md",
        },
        {
            "check_id": "top10_day83_alignment",
            "weight": 5,
            "passed": ("Day 82" in top10_text and "Day 83" in top10_text),
            "evidence": "Day 82 + Day 83 strategy chain",
        },
        {
            "check_id": "day82_summary_present",
            "weight": 10,
            "passed": day82_summary.exists(),
            "evidence": str(day82_summary),
        },
        {
            "check_id": "day82_delivery_board_present",
            "weight": 7,
            "passed": day82_board.exists(),
            "evidence": str(day82_board),
        },
        {
            "check_id": "day82_quality_floor",
            "weight": 13,
            "passed": day82_score >= 85 and day82_strict,
            "evidence": {
                "day82_score": day82_score,
                "strict_pass": day82_strict,
                "day82_checks": day82_check_count,
            },
        },
        {
            "check_id": "day82_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day82,
            "evidence": {"board_items": board_count, "contains_day82": board_has_day82},
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
            "check_id": "feedback_plan_data_present",
            "weight": 10,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day82_summary.exists() or not day82_board.exists():
        critical_failures.append("day82_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day82_score >= 85 and day82_strict:
        wins.append(f"Day 82 continuity baseline is stable with activation score={day82_score}.")
    else:
        misses.append("Day 82 continuity baseline is below the floor (<85) or not strict-pass.")
        handoff_actions.append(
            "Re-run Day 82 closeout command and raise baseline quality above 85 with strict pass before Day 83 lock."
        )

    if board_count >= 5 and board_has_day82:
        wins.append(
            f"Day 82 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 82 delivery board integrity is incomplete (needs >=5 items and Day 82 anchors)."
        )
        handoff_actions.append("Repair Day 82 delivery board entries to include Day 82 anchors.")

    if not missing_plan_keys:
        wins.append("Day 83 trust FAQ expansion dataset is available for launch execution.")
    else:
        misses.append("Day 83 trust FAQ expansion dataset is missing required keys.")
        handoff_actions.append(
            "Update .day83-trust-faq-expansion-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 83 trust FAQ expansion closeout lane is fully complete and ready for Day 84 evidence narrative priorities."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day83-trust-faq-expansion-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day82_summary": str(day82_summary.relative_to(root))
            if day82_summary.exists()
            else str(day82_summary),
            "day82_delivery_board": str(day82_board.relative_to(root))
            if day82_board.exists()
            else str(day82_board),
            "trust_faq_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "day82_activation_score": day82_score,
            "day82_checks": day82_check_count,
            "day82_delivery_board_items": board_count,
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
        "Day 83 trust FAQ expansion closeout summary",
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
        target / "day83-trust-faq-expansion-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "day83-trust-faq-expansion-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day83-trust-faq-brief.md", "# Day 83 trust FAQ brief\n")
    _write(target / "day83-trust-faq-expansion-plan.md", "# Day 83 trust FAQ expansion plan\n")
    _write(
        target / "day83-trust-template-upgrade-ledger.json",
        json.dumps({"upgrades": []}, indent=2) + "\n",
    )
    _write(
        target / "day83-escalation-outcomes-ledger.json",
        json.dumps({"outcomes": []}, indent=2) + "\n",
    )
    _write(target / "day83-trust-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day83-execution-log.md", "# Day 83 execution log\n")
    _write(
        target / "day83-delivery-board.md",
        "\n".join(["# Day 83 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day83-validation-commands.md",
        "# Day 83 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day83-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 83 trust FAQ expansion closeout checks")
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
        _write(root / _PAGE_PATH, _DAY83_DEFAULT_PAGE)

    payload = build_day83_trust_faq_expansion_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day83-trust-faq-expansion-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
