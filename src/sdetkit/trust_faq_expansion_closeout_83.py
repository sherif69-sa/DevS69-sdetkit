from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-trust-faq-expansion-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY82_SUMMARY_PATH = (
    "docs/artifacts/integration-feedback-closeout-pack/integration-feedback-closeout-summary.json"
)
_DAY82_BOARD_PATH = (
    "docs/artifacts/integration-feedback-closeout-pack/integration-feedback-delivery-board.md"
)
_PLAN_PATH = "docs/roadmap/plans/trust-faq-expansion-plan.json"
_SECTION_HEADER = "#  — Trust FAQ expansion loop closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Trust FAQ Expansion Closeout matters",
    "## Required inputs ()",
    "## Command lane",
    "## Trust FAQ expansion contract",
    "## Trust FAQ expansion quality checklist",
    "## Delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit trust-faq-expansion-closeout --format json --strict",
    "python -m sdetkit trust-faq-expansion-closeout --emit-pack-dir docs/artifacts/trust-faq-expansion-closeout-pack --format json --strict",
    "python -m sdetkit trust-faq-expansion-closeout --execute --evidence-dir docs/artifacts/trust-faq-expansion-closeout-pack/evidence --format json --strict",
    "python scripts/check_trust_faq_expansion_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit trust-faq-expansion-closeout --format json --strict",
    "python -m sdetkit trust-faq-expansion-closeout --emit-pack-dir docs/artifacts/trust-faq-expansion-closeout-pack --format json --strict",
    "python scripts/check_trust_faq_expansion_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for  trust FAQ expansion execution and signoff.",
    "The  lane references  outcomes, controls, and campaign continuity signals.",
    "Every  section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    " closeout records trust FAQ content upgrades, escalation outcomes, and  evidence narrative priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes baseline trust FAQ coverage, objection segmentation assumptions, and response SLA targets",
    "- [ ] Every trust lane row has owner, execution window, KPI threshold, and risk flag",
    "- [ ] CTA links point to trust docs/templates + runnable command evidence",
    "- [ ] Scorecard captures trust FAQ adoption delta, objection deflection delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes trust brief, FAQ expansion plan, template diffs, escalation ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ]  trust FAQ brief committed",
    "- [ ]  trust FAQ expansion plan committed",
    "- [ ]  trust template upgrade ledger exported",
    "- [ ]  escalation outcomes ledger exported",
    "- [ ]  evidence narrative priorities drafted from  outcomes",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"objection_channels"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DEFAULT_PAGE_TEMPLATE = "#  — Trust FAQ expansion loop closeout lane\n\n closes with a major upgrade that folds  integration feedback outcomes into trust FAQ coverage upgrades and escalation-readiness execution.\n\n## Why Trust FAQ Expansion Closeout matters\n\n- Turns  integration feedback outcomes into deterministic trust FAQ expansion loops across docs, templates, and support operations.\n- Protects quality with strict contract coverage, runnable commands, KPI thresholds, and rollback safety.\n- Creates a deterministic handoff from  closeout into  evidence narrative priorities.\n\n## Required inputs ()\n\n- `docs/artifacts/integration-feedback-closeout-pack/integration-feedback-closeout-summary.json`\n- `docs/artifacts/integration-feedback-closeout-pack/integration-feedback-delivery-board.md`\n- `docs/roadmap/plans/trust-faq-expansion-plan.json`\n\n## Command lane\n\n```bash\npython -m sdetkit trust-faq-expansion-closeout --format json --strict\npython -m sdetkit trust-faq-expansion-closeout --emit-pack-dir docs/artifacts/trust-faq-expansion-closeout-pack --format json --strict\npython -m sdetkit trust-faq-expansion-closeout --execute --evidence-dir docs/artifacts/trust-faq-expansion-closeout-pack/evidence --format json --strict\npython scripts/check_trust_faq_expansion_closeout_contract.py\n```\n\n## Trust FAQ expansion contract\n\n- Single owner + backup reviewer are assigned for  trust FAQ expansion execution and signoff.\n- The  lane references  outcomes, controls, and campaign continuity signals.\n- Every  section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n-  closeout records trust FAQ content upgrades, escalation outcomes, and  evidence narrative priorities.\n\n## Trust FAQ expansion quality checklist\n\n- [ ] Includes baseline trust FAQ coverage, objection segmentation assumptions, and response SLA targets\n- [ ] Every trust lane row has owner, execution window, KPI threshold, and risk flag\n- [ ] CTA links point to trust docs/templates + runnable command evidence\n- [ ] Scorecard captures trust FAQ adoption delta, objection deflection delta, confidence, and rollback owner\n- [ ] Artifact pack includes trust brief, FAQ expansion plan, template diffs, escalation ledger, KPI scorecard, and execution log\n\n## Delivery board\n\n- [ ]  trust FAQ brief committed\n- [ ]  trust FAQ expansion plan committed\n- [ ]  trust template upgrade ledger exported\n- [ ]  escalation outcomes ledger exported\n- [ ]  evidence narrative priorities drafted from  outcomes\n\n## Scoring model\n\nTrust FAQ Expansion Closeout weighted score (0-100):\n\n- Contract + command lane integrity (35)\n-  continuity baseline quality (35)\n- Feedback evidence data + delivery board completeness (30)\n"


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


def build_trust_faq_expansion_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read_text(root / "README.md")
    docs_index_text = _read_text(root / "docs/index.md")
    page_text = _read_text(root / _PAGE_PATH)
    top10_text = _read_text(root / _TOP10_PATH)

    integration_feedback_summary = root / _DAY82_SUMMARY_PATH
    integration_feedback_board = root / _DAY82_BOARD_PATH

    integration_feedback_data = _load_json(integration_feedback_summary)
    integration_feedback_summary_data = (
        integration_feedback_data.get("summary", {})
        if isinstance(integration_feedback_data.get("summary"), dict)
        else {}
    )
    integration_feedback_score = int(
        integration_feedback_summary_data.get("activation_score", 0) or 0
    )
    integration_feedback_strict = coerce_bool(
        integration_feedback_summary_data.get("strict_pass", False), default=False
    )
    integration_feedback_check_count = (
        len(integration_feedback_data.get("checks", []))
        if isinstance(integration_feedback_data.get("checks"), list)
        else 0
    )

    board_text = _read_text(integration_feedback_board)
    board_count = _checklist_count(board_text)
    board_has_integration_feedback = (
        "integration feedback" in board_text.lower() or "" in board_text
    )

    missing_sections = [section for section in _REQUIRED_SECTIONS if section not in page_text]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]
    missing_contract_lines = [line for line in _REQUIRED_CONTRACT_LINES if line not in page_text]
    missing_quality_lines = [line for line in _REQUIRED_QUALITY_LINES if line not in page_text]
    missing_board_items = [item for item in _REQUIRED_DELIVERY_BOARD_LINES if item not in page_text]

    plan_text = _read_text(root / _PLAN_PATH)
    missing_plan_keys = [key for key in _REQUIRED_DATA_KEYS if key not in plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_command_lane",
            "weight": 7,
            "passed": ("trust-faq-expansion-closeout" in readme_text),
            "evidence": "README trust-faq-expansion-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-83-big-upgrade-report.md" in docs_index_text
                and "integrations-trust-faq-expansion-closeout.md" in docs_index_text
            ),
            "evidence": "impact-83-big-upgrade-report.md + integrations-trust-faq-expansion-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ("" in top10_text and "" in top10_text),
            "evidence": " +  strategy chain",
        },
        {
            "check_id": "integration_feedback_summary_present",
            "weight": 10,
            "passed": integration_feedback_summary.exists(),
            "evidence": str(integration_feedback_summary),
        },
        {
            "check_id": "integration_feedback_delivery_board_present",
            "weight": 7,
            "passed": integration_feedback_board.exists(),
            "evidence": str(integration_feedback_board),
        },
        {
            "check_id": "integration_feedback_quality_floor",
            "weight": 13,
            "passed": integration_feedback_score >= 85 and integration_feedback_strict,
            "evidence": {
                "integration_feedback_score": integration_feedback_score,
                "strict_pass": integration_feedback_strict,
                "integration_feedback_checks": integration_feedback_check_count,
            },
        },
        {
            "check_id": "integration_feedback_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_integration_feedback,
            "evidence": {
                "board_items": board_count,
                "contains_integration_feedback": board_has_integration_feedback,
            },
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
    if not integration_feedback_summary.exists() or not integration_feedback_board.exists():
        critical_failures.append("integration_feedback_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if integration_feedback_score >= 85 and integration_feedback_strict:
        wins.append(
            f"Integration Feedback continuity baseline is stable with activation score={integration_feedback_score}."
        )
    else:
        misses.append(" continuity baseline is below the floor (<85) or not strict-pass.")
        handoff_actions.append(
            "Re-run  closeout command and raise baseline quality above 85 with strict pass before  lock."
        )

    if board_count >= 5 and board_has_integration_feedback:
        wins.append(f"82 delivery board integrity validated with {board_count} checklist items.")
    else:
        misses.append(" delivery board integrity is incomplete (needs >=5 items and  anchors).")
        handoff_actions.append("Repair  delivery board entries to include  anchors.")

    if not missing_plan_keys:
        wins.append(" trust FAQ expansion dataset is available for launch execution.")
    else:
        misses.append(" trust FAQ expansion dataset is missing required keys.")
        handoff_actions.append(
            "Update docs/roadmap/plans/trust-faq-expansion-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            " trust FAQ expansion closeout lane is fully complete and ready for  evidence narrative priorities."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "trust-faq-expansion-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "integration_feedback_summary": str(integration_feedback_summary.relative_to(root))
            if integration_feedback_summary.exists()
            else str(integration_feedback_summary),
            "integration_feedback_delivery_board": str(integration_feedback_board.relative_to(root))
            if integration_feedback_board.exists()
            else str(integration_feedback_board),
            "trust_faq_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "integration_feedback_activation_score": integration_feedback_score,
            "integration_feedback_checks": integration_feedback_check_count,
            "integration_feedback_delivery_board_items": board_count,
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
        " trust FAQ expansion closeout summary",
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
        target / "trust-faq-expansion-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "trust-faq-expansion-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "trust-faq-expansion-trust-faq-brief.md", "#  trust FAQ brief\n")
    _write(target / "trust-faq-expansion-plan.md", "#  trust FAQ expansion plan\n")
    _write(
        target / "trust-faq-expansion-trust-template-upgrade-ledger.json",
        json.dumps({"upgrades": []}, indent=2) + "\n",
    )
    _write(
        target / "trust-faq-expansion-escalation-outcomes-ledger.json",
        json.dumps({"outcomes": []}, indent=2) + "\n",
    )
    _write(
        target / "trust-faq-expansion-trust-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(target / "trust-faq-expansion-execution-log.md", "#  execution log\n")
    _write(
        target / "trust-faq-expansion-delivery-board.md",
        "\n".join(["#  delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "trust-faq-expansion-validation-commands.md",
        "#  validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "trust-faq-expansion-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_trust_faq_expansion_closeout_summary_impl(root: Path) -> dict[str, Any]:
    "Compatibility alias for legacy -based builder name."
    return build_trust_faq_expansion_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=" trust FAQ expansion closeout checks")
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
        _write(root / _PAGE_PATH, _DEFAULT_PAGE_TEMPLATE)

    payload = build_trust_faq_expansion_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/trust-faq-expansion-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
