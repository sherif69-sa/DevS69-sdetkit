from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-growth-campaign-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY80_SUMMARY_PATH = (
    "docs/artifacts/partner-outreach-closeout-pack/partner-outreach-closeout-summary.json"
)
_DAY80_BOARD_PATH = (
    "docs/artifacts/partner-outreach-closeout-pack/partner-outreach-delivery-board.md"
)
_PLAN_PATH = "docs/roadmap/plans/growth-campaign-plan.json"
_SECTION_HEADER = "#  — Growth campaign closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Growth Campaign Closeout matters",
    "## Required inputs ()",
    "## Command lane",
    "## Growth campaign contract",
    "## Growth campaign quality checklist",
    "## Delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit growth-campaign-closeout --format json --strict",
    "python -m sdetkit growth-campaign-closeout --emit-pack-dir docs/artifacts/growth-campaign-closeout-pack --format json --strict",
    "python -m sdetkit growth-campaign-closeout --execute --evidence-dir docs/artifacts/growth-campaign-closeout-pack/evidence --format json --strict",
    "python scripts/check_growth_campaign_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit growth-campaign-closeout --format json --strict",
    "python -m sdetkit growth-campaign-closeout --emit-pack-dir docs/artifacts/growth-campaign-closeout-pack --format json --strict",
    "python scripts/check_growth_campaign_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for  growth campaign execution and signoff.",
    "The  lane references  outcomes, controls, and KPI continuity signals.",
    "Every  section includes campaign CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    " closeout records campaign outcomes, confidence notes, and  execution priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes campaign baseline, audience assumptions, and launch cadence",
    "- [ ] Every campaign lane row has owner, execution window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures campaign score delta, partner carryover delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, campaign plan, execution ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ]  integration brief committed",
    "- [ ]  growth campaign plan committed",
    "- [ ]  campaign execution ledger exported",
    "- [ ]  campaign KPI scorecard snapshot exported",
    "- [ ]  execution priorities drafted from  learnings",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"campaign_tracks"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DEFAULT_PAGE_TEMPLATE = "#  — Growth campaign closeout lane\n\n closes with a major upgrade that converts  partner outreach outcomes into a growth-campaign execution pack.\n\n## Why Growth Campaign Closeout matters\n\n- Turns  partner outreach outcomes into growth campaign execution proof across docs, rollout, and demand loops.\n- Protects launch quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.\n- Creates a deterministic handoff from  growth campaign closeout into  execution priorities.\n\n## Required inputs ()\n\n- `docs/artifacts/partner-outreach-closeout-pack/partner-outreach-closeout-summary.json`\n- `docs/artifacts/partner-outreach-closeout-pack/partner-outreach-delivery-board.md`\n- `docs/roadmap/plans/growth-campaign-plan.json`\n\n## Command lane\n\n```bash\npython -m sdetkit growth-campaign-closeout --format json --strict\npython -m sdetkit growth-campaign-closeout --emit-pack-dir docs/artifacts/growth-campaign-closeout-pack --format json --strict\npython -m sdetkit growth-campaign-closeout --execute --evidence-dir docs/artifacts/growth-campaign-closeout-pack/evidence --format json --strict\npython scripts/check_growth_campaign_closeout_contract.py\n```\n\n## Growth campaign contract\n\n- Single owner + backup reviewer are assigned for  growth campaign execution and signoff.\n- The  lane references  outcomes, controls, and KPI continuity signals.\n- Every  section includes campaign CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n-  closeout records campaign outcomes, confidence notes, and  execution priorities.\n\n## Growth campaign quality checklist\n\n- [ ] Includes campaign baseline, audience assumptions, and launch cadence\n- [ ] Every campaign lane row has owner, execution window, KPI threshold, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures campaign score delta, partner carryover delta, confidence, and rollback owner\n- [ ] Artifact pack includes integration brief, campaign plan, execution ledger, KPI scorecard, and execution log\n\n## Delivery board\n\n- [ ]  integration brief committed\n- [ ]  growth campaign plan committed\n- [ ]  campaign execution ledger exported\n- [ ]  campaign KPI scorecard snapshot exported\n- [ ]  execution priorities drafted from  learnings\n\n## Scoring model\n\nGrowth Campaign Closeout weighted score (0-100):\n\n- Contract + command lane integrity (35)\n-  continuity baseline quality (35)\n- Campaign evidence data + delivery board completeness (30)\n"


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def _checklist_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip().startswith("- ["))


def build_growth_campaign_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read_text(root / "README.md")
    docs_index_text = _read_text(root / "docs/index.md")
    page_text = _read_text(root / _PAGE_PATH)
    top10_text = _read_text(root / _TOP10_PATH)

    partner_outreach_summary = root / _DAY80_SUMMARY_PATH
    partner_outreach_board = root / _DAY80_BOARD_PATH

    partner_outreach_payload = _load_json(partner_outreach_summary)
    partner_outreach_score = int(
        partner_outreach_payload.get("summary", {}).get("activation_score", 0) or 0
    )
    partner_outreach_strict = bool(
        partner_outreach_payload.get("summary", {}).get("strict_pass", False)
    )
    partner_outreach_check_count = len(partner_outreach_payload.get("checks", []))

    board_text = _read_text(partner_outreach_board)
    board_count = _checklist_count(board_text)
    board_has_partner_outreach = "partner outreach" in board_text.lower() or "" in board_text

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
            "passed": ("growth-campaign-closeout" in readme_text),
            "evidence": "README growth-campaign-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-81-big-upgrade-report.md" in docs_index_text
                and "integrations-growth-campaign-closeout.md" in docs_index_text
            ),
            "evidence": "impact-81-big-upgrade-report.md + integrations-growth-campaign-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ("" in top10_text and "" in top10_text),
            "evidence": " +  strategy chain",
        },
        {
            "check_id": "partner_outreach_summary_present",
            "weight": 10,
            "passed": partner_outreach_summary.exists(),
            "evidence": str(partner_outreach_summary),
        },
        {
            "check_id": "partner_outreach_delivery_board_present",
            "weight": 7,
            "passed": partner_outreach_board.exists(),
            "evidence": str(partner_outreach_board),
        },
        {
            "check_id": "partner_outreach_quality_floor",
            "weight": 13,
            "passed": partner_outreach_score >= 85,
            "evidence": {
                "partner_outreach_score": partner_outreach_score,
                "strict_pass": partner_outreach_strict,
                "partner_outreach_checks": partner_outreach_check_count,
            },
        },
        {
            "check_id": "partner_outreach_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_partner_outreach,
            "evidence": {
                "board_items": board_count,
                "contains_partner_outreach": board_has_partner_outreach,
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
            "check_id": "campaign_plan_data_present",
            "weight": 10,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not partner_outreach_summary.exists() or not partner_outreach_board.exists():
        critical_failures.append("partner_outreach_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if partner_outreach_score >= 85:
        wins.append(
            f"Partner Outreach continuity baseline is stable with activation score={partner_outreach_score}."
        )
    else:
        misses.append(" continuity baseline is below the floor (<85).")
        handoff_actions.append(
            "Re-run  closeout command and raise baseline quality above 85 before  lock."
        )

    if board_count >= 5 and board_has_partner_outreach:
        wins.append(f"80 delivery board integrity validated with {board_count} checklist items.")
    else:
        misses.append(" delivery board integrity is incomplete (needs >=5 items and  anchors).")
        handoff_actions.append("Repair  delivery board entries to include  anchors.")

    if not missing_plan_keys:
        wins.append(" growth campaign dataset is available for launch execution.")
    else:
        misses.append(" growth campaign dataset is missing required keys.")
        handoff_actions.append(
            "Update docs/roadmap/plans/growth-campaign-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            " growth campaign closeout lane is fully complete and ready for  execution priorities."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "growth-campaign-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "partner_outreach_summary": str(partner_outreach_summary.relative_to(root))
            if partner_outreach_summary.exists()
            else str(partner_outreach_summary),
            "partner_outreach_delivery_board": str(partner_outreach_board.relative_to(root))
            if partner_outreach_board.exists()
            else str(partner_outreach_board),
            "growth_campaign_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "partner_outreach_activation_score": partner_outreach_score,
            "partner_outreach_checks": partner_outreach_check_count,
            "partner_outreach_delivery_board_items": board_count,
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
        " growth campaign closeout summary",
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
    _write(target / "growth-campaign-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "growth-campaign-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "growth-campaign-integration-brief.md", "#  integration brief\n")
    _write(target / "growth-campaign-plan.md", "#  growth campaign plan\n")
    _write(
        target / "growth-campaign-campaign-execution-ledger.json",
        json.dumps({"executions": []}, indent=2) + "\n",
    )
    _write(
        target / "growth-campaign-campaign-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(target / "growth-campaign-execution-log.md", "#  execution log\n")
    _write(
        target / "growth-campaign-delivery-board.md",
        "\n".join(["#  delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "growth-campaign-validation-commands.md",
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
        out_dir / "growth-campaign-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_growth_campaign_closeout_summary_impl(root: Path) -> dict[str, Any]:
    "Compatibility alias for legacy -based builder name."
    return build_growth_campaign_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=" growth campaign closeout checks")
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

    payload = build_growth_campaign_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/growth-campaign-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
