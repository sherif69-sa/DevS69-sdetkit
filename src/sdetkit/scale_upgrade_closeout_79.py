from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-scale-upgrade-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY78_SUMMARY_PATH = (
    "docs/artifacts/ecosystem-priorities-closeout-pack/ecosystem-priorities-closeout-summary.json"
)
_DAY78_BOARD_PATH = (
    "docs/artifacts/ecosystem-priorities-closeout-pack/ecosystem-priorities-delivery-board.md"
)
_PLAN_PATH = "docs/roadmap/plans/scale-upgrade-plan.json"
_SECTION_HEADER = "# Scale upgrade closeout lane"
_REQUIRED_SECTIONS = [
    "## Why scale upgrade matters",
    "## Required inputs ()",
    "## Scale upgrade command lane",
    "## Scale upgrade contract",
    "## Scale upgrade quality checklist",
    "## Scale upgrade delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit scale-upgrade-closeout --format json --strict",
    "python -m sdetkit scale-upgrade-closeout --emit-pack-dir docs/artifacts/scale-upgrade-closeout-pack --format json --strict",
    "python -m sdetkit scale-upgrade-closeout --execute --evidence-dir docs/artifacts/scale-upgrade-closeout-pack/evidence --format json --strict",
    "python scripts/check_scale_upgrade_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit scale-upgrade-closeout --format json --strict",
    "python -m sdetkit scale-upgrade-closeout --emit-pack-dir docs/artifacts/scale-upgrade-closeout-pack --format json --strict",
    "python scripts/check_scale_upgrade_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for  scale upgrade execution and signoff.",
    "The  lane references  outcomes, controls, and KPI continuity signals.",
    "Every  section includes enterprise CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    " closeout records enterprise onboarding outcomes, confidence notes, and  partner outreach priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes enterprise onboarding baseline, role coverage cadence, and stakeholder assumptions",
    "- [ ] Every scale lane row has owner, execution window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures scale score delta, ecosystem carryover delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, scale upgrade plan, execution ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ]  integration brief committed",
    "- [ ]  scale upgrade plan committed",
    "- [ ]  enterprise execution ledger exported",
    "- [ ]  enterprise KPI scorecard snapshot exported",
    "- [ ]  partner outreach priorities drafted from  learnings",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"scale_tracks"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DEFAULT_PAGE_TEMPLATE = "# Scale upgrade closeout lane\n\n closes with a major upgrade that converts  ecosystem priorities into an enterprise-scale onboarding execution pack.\n\n## Why scale upgrade matters\n\n- Turns  ecosystem priorities into enterprise onboarding readiness proof across docs, rollout, and adoption loops.\n- Protects scale quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.\n- Creates a deterministic handoff from  scale upgrades into  partner outreach priorities.\n\n## Required inputs ()\n\n- `docs/artifacts/ecosystem-priorities-closeout-pack/ecosystem-priorities-closeout-summary.json`\n- `docs/artifacts/ecosystem-priorities-closeout-pack/ecosystem-priorities-delivery-board.md`\n- `docs/roadmap/plans/scale-upgrade-plan.json`\n\n## Scale upgrade command lane\n\n```bash\npython -m sdetkit scale-upgrade-closeout --format json --strict\npython -m sdetkit scale-upgrade-closeout --emit-pack-dir docs/artifacts/scale-upgrade-closeout-pack --format json --strict\npython -m sdetkit scale-upgrade-closeout --execute --evidence-dir docs/artifacts/scale-upgrade-closeout-pack/evidence --format json --strict\npython scripts/check_scale_upgrade_closeout_contract.py\n```\n\n## Scale upgrade contract\n\n- Single owner + backup reviewer are assigned for  scale upgrade execution and signoff.\n- The  lane references  outcomes, controls, and KPI continuity signals.\n- Every  section includes enterprise CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n-  closeout records enterprise onboarding outcomes, confidence notes, and  partner outreach priorities.\n\n## Scale upgrade quality checklist\n\n- [ ] Includes enterprise onboarding baseline, role coverage cadence, and stakeholder assumptions\n- [ ] Every scale lane row has owner, execution window, KPI threshold, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures scale score delta, ecosystem carryover delta, confidence, and rollback owner\n- [ ] Artifact pack includes integration brief, scale upgrade plan, execution ledger, KPI scorecard, and execution log\n\n## Scale upgrade delivery board\n\n- [ ]  integration brief committed\n- [ ]  scale upgrade plan committed\n- [ ]  enterprise execution ledger exported\n- [ ]  enterprise KPI scorecard snapshot exported\n- [ ]  partner outreach priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Contract + command lane integrity (35)\n-  continuity baseline quality (35)\n- Scale evidence data + delivery board completeness (30)\n"


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
    except Exception:
        return {}


def build_scale_upgrade_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read_text(root / "README.md")
    docs_index_text = _read_text(root / "docs/index.md")
    page_text = _read_text(root / _PAGE_PATH)
    top10_text = _read_text(root / _TOP10_PATH)

    ecosystem_priorities_summary = root / _DAY78_SUMMARY_PATH
    ecosystem_priorities_board = root / _DAY78_BOARD_PATH
    plan_path = root / _PLAN_PATH

    ecosystem_priorities_payload = _load_json(ecosystem_priorities_summary)
    ecosystem_priorities_score = int(
        ecosystem_priorities_payload.get("summary", {}).get("activation_score", 0) or 0
    )
    ecosystem_priorities_strict = bool(
        ecosystem_priorities_payload.get("summary", {}).get("strict_pass", False)
    )
    ecosystem_priorities_check_count = len(ecosystem_priorities_payload.get("checks", []))

    board_text = _read_text(ecosystem_priorities_board)
    board_count = sum(1 for line in board_text.splitlines() if line.strip().startswith("- [ ]"))
    board_has_ecosystem_priorities = "ecosystem priorities" in board_text.lower()

    plan_text = _read_text(plan_path)

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_plan_keys = [x for x in _REQUIRED_DATA_KEYS if x not in plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_scale_upgrade_command",
            "weight": 7,
            "passed": ("scale-upgrade-closeout" in readme_text),
            "evidence": "README scale-upgrade command lane",
        },
        {
            "check_id": "docs_index_scale_upgrade_links",
            "weight": 8,
            "passed": (
                "impact-79-big-upgrade-report.md" in docs_index_text
                and "integrations-scale-upgrade-closeout.md" in docs_index_text
            ),
            "evidence": "impact-79-big-upgrade-report.md + integrations-scale-upgrade-closeout.md",
        },
        {
            "check_id": "top10_scale_upgrade_alignment",
            "weight": 5,
            "passed": ("Ecosystem priorities + scale upgrade strategy chain" in top10_text),
            "evidence": "Ecosystem priorities + scale upgrade strategy chain",
        },
        {
            "check_id": "ecosystem_priorities_summary_present",
            "weight": 10,
            "passed": ecosystem_priorities_summary.exists(),
            "evidence": str(ecosystem_priorities_summary),
        },
        {
            "check_id": "ecosystem_priorities_delivery_board_present",
            "weight": 7,
            "passed": ecosystem_priorities_board.exists(),
            "evidence": str(ecosystem_priorities_board),
        },
        {
            "check_id": "ecosystem_priorities_quality_floor",
            "weight": 13,
            "passed": ecosystem_priorities_score >= 85,
            "evidence": {
                "ecosystem_priorities_score": ecosystem_priorities_score,
                "strict_pass": ecosystem_priorities_strict,
                "ecosystem_priorities_checks": ecosystem_priorities_check_count,
            },
        },
        {
            "check_id": "ecosystem_priorities_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_ecosystem_priorities,
            "evidence": {
                "board_items": board_count,
                "contains_ecosystem_priorities": board_has_ecosystem_priorities,
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
            "check_id": "scale_plan_data_present",
            "weight": 10,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not ecosystem_priorities_summary.exists() or not ecosystem_priorities_board.exists():
        critical_failures.append("ecosystem_priorities_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if ecosystem_priorities_score >= 85:
        wins.append(
            f"Ecosystem Priorities continuity baseline is stable with activation score={ecosystem_priorities_score}."
        )
    else:
        misses.append(" continuity baseline is below the floor (<85).")
        handoff_actions.append(
            "Re-run  closeout command and raise baseline quality above 85 before  lock."
        )

    if board_count >= 5 and board_has_ecosystem_priorities:
        wins.append(f"78 delivery board integrity validated with {board_count} checklist items.")
    else:
        misses.append(" delivery board integrity is incomplete (needs >=5 items and  anchors).")
        handoff_actions.append("Repair  delivery board entries to include  anchors.")

    if not missing_plan_keys:
        wins.append(" scale upgrade dataset is available for launch execution.")
    else:
        misses.append(" scale upgrade dataset is missing required keys.")
        handoff_actions.append(
            "Update docs/roadmap/plans/scale-upgrade-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            " scale upgrade closeout lane is fully complete and ready for  partner outreach priorities."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "scale-upgrade-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "ecosystem_priorities_summary": str(ecosystem_priorities_summary.relative_to(root))
            if ecosystem_priorities_summary.exists()
            else str(ecosystem_priorities_summary),
            "ecosystem_priorities_delivery_board": str(ecosystem_priorities_board.relative_to(root))
            if ecosystem_priorities_board.exists()
            else str(ecosystem_priorities_board),
            "scale_upgrade_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "ecosystem_priorities_activation_score": ecosystem_priorities_score,
            "ecosystem_priorities_checks": ecosystem_priorities_check_count,
            "ecosystem_priorities_delivery_board_items": board_count,
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
        "Scale Upgrade Closeout summary",
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
    _write(target / "scale-upgrade-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "scale-upgrade-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "scale-upgrade-integration-brief.md", "# Scale upgrade integration brief\n")
    _write(target / "scale-upgrade-plan.md", "# Scale upgrade plan\n")
    _write(
        target / "scale-upgrade-enterprise-execution-ledger.json",
        json.dumps({"executions": []}, indent=2) + "\n",
    )
    _write(
        target / "scale-upgrade-enterprise-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(target / "scale-upgrade-execution-log.md", "# Scale upgrade execution log\n")
    _write(
        target / "scale-upgrade-delivery-board.md",
        "\n".join(["# Scale upgrade delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "scale-upgrade-validation-commands.md",
        "# Scale upgrade validation commands\n\n```bash\n"
        + "\n".join(_EXECUTION_COMMANDS)
        + "\n```\n",
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
        out_dir / "scale-upgrade-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_scale_upgrade_closeout_summary_impl(root: Path) -> dict[str, Any]:
    "Compatibility alias for legacy -based builder name."
    return build_scale_upgrade_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scale Upgrade Closeout checks")
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

    payload = build_scale_upgrade_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/scale-upgrade-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
