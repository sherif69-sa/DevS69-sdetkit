from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-phase3-wrap-publication-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_GOVERNANCE_SCALE_SUMMARY_PATH = (
    "docs/artifacts/governance-scale-closeout-pack/governance-scale-closeout-summary.json"
)
_GOVERNANCE_SCALE_BOARD_PATH = (
    "docs/artifacts/governance-scale-closeout-pack/governance-scale-delivery-board.md"
)
_PLAN_PATH = "docs/roadmap/plans/phase3-wrap-publication-plan.json"
_CANONICAL_PACK_DIR = "docs/artifacts/phase3-wrap-publication-closeout-pack"
_CANONICAL_SUMMARY_NAME = "phase3-wrap-publication-closeout-summary.json"
_CANONICAL_BOARD_NAME = "phase3-wrap-publication-delivery-board.md"
_CANONICAL_EVIDENCE_SUMMARY_NAME = "phase3-wrap-publication-execution-summary.json"
_SECTION_HEADER = "#  — Phase-3 wrap publication closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Phase3 Wrap Publication Closeout matters",
    "## Required inputs ()",
    "## Command lane",
    "## Phase-3 wrap publication contract",
    "## Phase-3 wrap publication quality checklist",
    "## Delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit phase3-wrap-publication-closeout --format json --strict",
    "python -m sdetkit phase3-wrap-publication-closeout --emit-pack-dir docs/artifacts/phase3-wrap-publication-closeout-pack --format json --strict",
    "python -m sdetkit phase3-wrap-publication-closeout --execute --evidence-dir docs/artifacts/phase3-wrap-publication-closeout-pack/evidence --format json --strict",
    "python scripts/check_phase3_wrap_publication_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit phase3-wrap-publication-closeout --format json --strict",
    "python -m sdetkit phase3-wrap-publication-closeout --emit-pack-dir docs/artifacts/phase3-wrap-publication-closeout-pack --format json --strict",
    "python scripts/check_phase3_wrap_publication_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for  phase-3 wrap publication execution and signoff.",
    "The  lane references  outcomes, controls, and trust continuity signals.",
    "Every  section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    " closeout records phase-3 wrap publication outputs, final report publication status, and next-impact roadmap inputs.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes baseline evidence coverage, objection segmentation assumptions, and response SLA targets",
    "- [ ] Every narrative lane row has owner, execution window, KPI threshold, and risk flag",
    "- [ ] CTA links point to narrative docs/templates + runnable command evidence",
    "- [ ] Scorecard captures phase-3 wrap publication adoption delta, objection deflection delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes narrative brief, evidence plan, template diffs, outcome ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ]  evidence brief committed",
    "- [ ]  phase-3 wrap publication plan committed",
    "- [ ]  narrative template upgrade ledger exported",
    "- [ ]  storyline outcomes ledger exported",
    "- [ ] Next-impact roadmap draft captured from  outcomes",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"narrative_channels"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DEFAULT_PAGE_TEMPLATE = "#  — Phase-3 wrap publication closeout lane\n\n closes with a major upgrade that converts  governance scale outcomes into a deterministic phase-3 wrap and publication operating lane.\n\n## Why Phase3 Wrap Publication Closeout matters\n\n- Converts  governance scale outcomes into reusable publication decisions across release recap, roadmap governance, and maintainer escalation paths.\n- Protects quality with strict contract coverage, runnable commands, KPI thresholds, and rollback safety.\n- Creates a deterministic handoff from  closeout into the next-impact roadmap.\n\n## Required inputs ()\n\n- `docs/artifacts/governance-scale-closeout-pack/governance-scale-closeout-summary.json`\n- `docs/artifacts/governance-scale-closeout-pack/governance-scale-delivery-board.md`\n- `docs/roadmap/plans/phase3-wrap-publication-plan.json`\n\n## Command lane\n\n```bash\npython -m sdetkit phase3-wrap-publication-closeout --format json --strict\npython -m sdetkit phase3-wrap-publication-closeout --emit-pack-dir docs/artifacts/phase3-wrap-publication-closeout-pack --format json --strict\npython -m sdetkit phase3-wrap-publication-closeout --execute --evidence-dir docs/artifacts/phase3-wrap-publication-closeout-pack/evidence --format json --strict\npython scripts/check_phase3_wrap_publication_closeout_contract.py\n```\n\n## Phase-3 wrap publication contract\n\n- Single owner + backup reviewer are assigned for  phase-3 wrap publication execution and signoff.\n- The  lane references  outcomes, controls, and trust continuity signals.\n- Every  section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n-  closeout records phase-3 wrap publication outputs, final report publication status, and next-impact roadmap inputs.\n\n## Phase-3 wrap publication quality checklist\n\n- [ ] Includes baseline evidence coverage, objection segmentation assumptions, and response SLA targets\n- [ ] Every narrative lane row has owner, execution window, KPI threshold, and risk flag\n- [ ] CTA links point to narrative docs/templates + runnable command evidence\n- [ ] Scorecard captures phase-3 wrap publication adoption delta, objection deflection delta, confidence, and rollback owner\n- [ ] Artifact pack includes narrative brief, evidence plan, template diffs, outcome ledger, KPI scorecard, and execution log\n\n## Delivery board\n\n- [ ]  evidence brief committed\n- [ ]  phase-3 wrap publication plan committed\n- [ ]  narrative template upgrade ledger exported\n- [ ]  storyline outcomes ledger exported\n- [ ] Next-impact roadmap draft captured from  outcomes\n\n## Scoring model\n\n weights continuity + execution contract + governance artifact readiness for a 100-point activation score.\n"


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


def build_phase3_wrap_publication_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read_text(root / "README.md")
    docs_index_text = _read_text(root / "docs/index.md")
    page_text = _read_text(root / _PAGE_PATH)
    top10_text = _read_text(root / _TOP10_PATH)

    governance_scale_summary = root / _GOVERNANCE_SCALE_SUMMARY_PATH
    governance_scale_board = root / _GOVERNANCE_SCALE_BOARD_PATH

    governance_scale_data = _load_json(governance_scale_summary)
    governance_scale_summary_data = (
        governance_scale_data.get("summary", {})
        if isinstance(governance_scale_data.get("summary"), dict)
        else {}
    )
    governance_scale_score = int(governance_scale_summary_data.get("activation_score", 0) or 0)
    governance_scale_strict = coerce_bool(
        governance_scale_summary_data.get("strict_pass", False), default=False
    )
    governance_scale_check_count = (
        len(governance_scale_data.get("checks", []))
        if isinstance(governance_scale_data.get("checks"), list)
        else 0
    )

    board_text = _read_text(governance_scale_board)
    board_count = _checklist_count(board_text)
    board_has_governance_scale = "governance scale" in board_text.lower()

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
            "passed": ("phase3-wrap-publication-closeout" in readme_text),
            "evidence": "README phase3-wrap-publication-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-90-big-upgrade-report.md" in docs_index_text
                and "integrations-phase3-wrap-publication-closeout.md" in docs_index_text
            ),
            "evidence": "impact-90-big-upgrade-report.md + integrations-phase3-wrap-publication-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ("" in top10_text and "" in top10_text),
            "evidence": " +  strategy chain",
        },
        {
            "check_id": "governance_scale_summary_present",
            "weight": 10,
            "passed": governance_scale_summary.exists(),
            "evidence": str(governance_scale_summary),
        },
        {
            "check_id": "governance_scale_delivery_board_present",
            "weight": 7,
            "passed": governance_scale_board.exists(),
            "evidence": str(governance_scale_board),
        },
        {
            "check_id": "governance_scale_quality_floor",
            "weight": 13,
            "passed": governance_scale_score >= 85 and governance_scale_strict,
            "evidence": {
                "governance_scale_score": governance_scale_score,
                "strict_pass": governance_scale_strict,
                "governance_scale_checks": governance_scale_check_count,
            },
        },
        {
            "check_id": "governance_scale_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_governance_scale,
            "evidence": {
                "board_items": board_count,
                "contains_governance_scale": board_has_governance_scale,
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
            "check_id": "evidence_plan_data_present",
            "weight": 10,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not governance_scale_summary.exists() or not governance_scale_board.exists():
        critical_failures.append("governance_scale_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if governance_scale_score >= 85 and governance_scale_strict:
        wins.append(
            f"89 continuity baseline is stable with activation score={governance_scale_score}."
        )
    else:
        misses.append(" continuity baseline is below the floor (<85) or not strict-pass.")
        handoff_actions.append(
            "Re-run  closeout command and raise baseline quality above 85 with strict pass before  lock."
        )

    if board_count >= 5 and board_has_governance_scale:
        wins.append(
            f"Governance scale delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(" delivery board integrity is incomplete (needs >=5 items and  anchors).")
        handoff_actions.append("Repair  delivery board entries to include  anchors.")

    if not missing_plan_keys:
        wins.append(" phase-3 wrap publication dataset is available for governance execution.")
    else:
        misses.append(" phase-3 wrap publication dataset is missing required keys.")
        handoff_actions.append(
            "Update docs/roadmap/plans/phase3-wrap-publication-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            " phase-3 wrap publication closeout lane is fully complete and ready for next-impact roadmap execution."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "phase3-wrap-publication-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "governance_scale_summary": str(governance_scale_summary.relative_to(root))
            if governance_scale_summary.exists()
            else str(governance_scale_summary),
            "governance_scale_delivery_board": str(governance_scale_board.relative_to(root))
            if governance_scale_board.exists()
            else str(governance_scale_board),
            "phase3_wrap_publication_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "governance_scale_activation_score": governance_scale_score,
            "governance_scale_checks": governance_scale_check_count,
            "governance_scale_delivery_board_items": board_count,
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
        " phase-3 wrap publication closeout summary",
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
        target / _CANONICAL_SUMMARY_NAME,
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "phase3-wrap-publication-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "phase3-wrap-publication-evidence-brief.md",
        "#  phase-3 wrap publication brief\n",
    )
    _write(target / "phase3-wrap-publication-plan.md", "#  phase-3 wrap publication plan\n")
    _write(
        target / "phase3-wrap-publication-narrative-template-upgrade-ledger.json",
        json.dumps({"upgrades": []}, indent=2) + "\n",
    )
    _write(
        target / "phase3-wrap-publication-storyline-outcomes-ledger.json",
        json.dumps({"outcomes": []}, indent=2) + "\n",
    )
    _write(
        target / "phase3-wrap-publication-narrative-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(target / "phase3-wrap-publication-execution-log.md", "#  execution log\n")
    _write(
        target / _CANONICAL_BOARD_NAME,
        "\n".join(["#  delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "phase3-wrap-publication-validation-commands.md",
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
        out_dir / _CANONICAL_EVIDENCE_SUMMARY_NAME,
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_phase3_wrap_publication_closeout_summary_impl(root: Path) -> dict[str, Any]:
    "Compatibility alias for legacy -based builder name."
    return build_phase3_wrap_publication_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=" phase-3 wrap publication closeout checks")
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

    payload = build_phase3_wrap_publication_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/phase3-wrap-publication-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
