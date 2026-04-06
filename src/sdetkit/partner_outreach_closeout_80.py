from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-partner-outreach-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY79_SUMMARY_PATH = (
    "docs/artifacts/scale-upgrade-closeout-pack/scale-upgrade-closeout-summary.json"
)
_DAY79_BOARD_PATH = "docs/artifacts/scale-upgrade-closeout-pack/scale-upgrade-delivery-board.md"
_PLAN_PATH = "docs/roadmap/plans/partner-outreach-plan.json"
_SECTION_HEADER = "# Partner outreach closeout lane"
_REQUIRED_SECTIONS = [
    "## Why partner outreach matters",
    "## Required inputs",
    "## Partner outreach command lane",
    "## Partner outreach contract",
    "## Partner outreach quality checklist",
    "## Partner outreach delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit partner-outreach-closeout --format json --strict",
    "python -m sdetkit partner-outreach-closeout --emit-pack-dir docs/artifacts/partner-outreach-closeout-pack --format json --strict",
    "python -m sdetkit partner-outreach-closeout --execute --evidence-dir docs/artifacts/partner-outreach-closeout-pack/evidence --format json --strict",
    "python scripts/check_partner_outreach_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit partner-outreach-closeout --format json --strict",
    "python -m sdetkit partner-outreach-closeout --emit-pack-dir docs/artifacts/partner-outreach-closeout-pack --format json --strict",
    "python scripts/check_partner_outreach_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for partner outreach execution and signoff.",
    "The lane references prior outcomes, controls, and KPI continuity signals.",
    "Every section includes partner CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Closeout records partner onboarding outcomes, confidence notes, and growth campaign priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes partner onboarding baseline, enablement cadence, and stakeholder assumptions",
    "- [ ] Every partner lane row has owner, execution window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures partner score delta, scale carryover delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, partner outreach plan, execution ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Integration brief committed",
    "- [ ] Partner outreach plan committed",
    "- [ ] Partner execution ledger exported",
    "- [ ] Partner KPI scorecard snapshot exported",
    "- [ ] Growth campaign priorities drafted from partner outreach learnings",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"partner_tracks"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DEFAULT_PAGE_TEMPLATE = """# Partner outreach closeout lane

Partner outreach closes with a major upgrade that converts prior scale outcomes into a partner-outreach execution pack.

## Why partner outreach matters

- Turns prior scale outcomes into partner onboarding proof across docs, rollout, and adoption loops.
- Protects launch quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.
- Creates a deterministic handoff from partner outreach into growth campaign priorities.

## Required inputs

- `docs/artifacts/scale-upgrade-closeout-pack/scale-upgrade-closeout-summary.json`
- `docs/artifacts/scale-upgrade-closeout-pack/scale-upgrade-delivery-board.md`
- `docs/roadmap/plans/partner-outreach-plan.json`

## Partner outreach command lane

```bash
python -m sdetkit partner-outreach-closeout --format json --strict
python -m sdetkit partner-outreach-closeout --emit-pack-dir docs/artifacts/partner-outreach-closeout-pack --format json --strict
python -m sdetkit partner-outreach-closeout --execute --evidence-dir docs/artifacts/partner-outreach-closeout-pack/evidence --format json --strict
python scripts/check_partner_outreach_closeout_contract.py
```

## Partner outreach contract

- Single owner + backup reviewer are assigned for partner outreach execution and signoff.
- The lane references prior outcomes, controls, and KPI continuity signals.
- Every section includes partner CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Closeout records partner onboarding outcomes, confidence notes, and growth campaign priorities.

## Partner outreach quality checklist

- [ ] Includes partner onboarding baseline, enablement cadence, and stakeholder assumptions
- [ ] Every partner lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures partner score delta, scale carryover delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, partner outreach plan, execution ledger, KPI scorecard, and execution log

## Partner outreach delivery board

- [ ] Integration brief committed
- [ ] Partner outreach plan committed
- [ ] Partner execution ledger exported
- [ ] Partner KPI scorecard snapshot exported
- [ ] Growth campaign priorities drafted from partner outreach learnings

## Scoring model

Weighted score (0-100):

- Contract + command lane integrity (35)
- Prior continuity baseline quality (35)
- Partner evidence data + delivery board completeness (30)
"""


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


def build_partner_outreach_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read_text(root / "README.md")
    docs_index_text = _read_text(root / "docs/index.md")
    page_text = _read_text(root / _PAGE_PATH)
    top10_text = _read_text(root / _TOP10_PATH)

    scale_upgrade_summary = root / _DAY79_SUMMARY_PATH
    scale_upgrade_board = root / _DAY79_BOARD_PATH
    scale_upgrade_payload = _load_json(scale_upgrade_summary)
    scale_upgrade_score = int(
        scale_upgrade_payload.get("summary", {}).get("activation_score", 0) or 0
    )
    scale_upgrade_strict = coerce_bool(scale_upgrade_payload.get("summary", {}).get("strict_pass", False), default=False)
    scale_upgrade_check_count = (
        len(scale_upgrade_payload.get("checks", []))
        if isinstance(scale_upgrade_payload.get("checks", []), list)
        else 0
    )

    board_lines = [
        line.strip()
        for line in _read_text(scale_upgrade_board).splitlines()
        if line.strip().startswith("- [")
    ]
    board_count = len(board_lines)
    board_has_scale_upgrade = any("scale" in line.lower() for line in board_lines)

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
            "passed": ("partner-outreach-closeout" in readme_text),
            "evidence": "README partner-outreach command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-80-big-upgrade-report.md" in docs_index_text
                and "integrations-partner-outreach-closeout.md" in docs_index_text
            ),
            "evidence": "impact-80-big-upgrade-report.md + integrations-partner-outreach-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ("Scale upgrade + partner outreach strategy chain" in top10_text),
            "evidence": "Scale upgrade + partner outreach strategy chain",
        },
        {
            "check_id": "scale_upgrade_summary_present",
            "weight": 10,
            "passed": scale_upgrade_summary.exists(),
            "evidence": str(scale_upgrade_summary),
        },
        {
            "check_id": "scale_upgrade_delivery_board_present",
            "weight": 7,
            "passed": scale_upgrade_board.exists(),
            "evidence": str(scale_upgrade_board),
        },
        {
            "check_id": "scale_upgrade_quality_floor",
            "weight": 13,
            "passed": scale_upgrade_score >= 85,
            "evidence": {
                "scale_upgrade_score": scale_upgrade_score,
                "strict_pass": scale_upgrade_strict,
                "scale_upgrade_checks": scale_upgrade_check_count,
            },
        },
        {
            "check_id": "scale_upgrade_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_scale_upgrade,
            "evidence": {
                "board_items": board_count,
                "contains_scale_upgrade": board_has_scale_upgrade,
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
            "check_id": "partner_plan_data_present",
            "weight": 10,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not scale_upgrade_summary.exists() or not scale_upgrade_board.exists():
        critical_failures.append("scale_upgrade_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if scale_upgrade_score >= 85:
        wins.append(
            f"Scale Upgrade continuity baseline is stable with activation score={scale_upgrade_score}."
        )
    else:
        misses.append("Prior continuity baseline is below the floor (<85).")
        handoff_actions.append(
            "Re-run prior closeout command and raise baseline quality above 85 before lock."
        )

    if board_count >= 5 and board_has_scale_upgrade:
        wins.append(
            f"Prior delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Prior delivery board integrity is incomplete (needs >=5 items and prior anchors)."
        )
        handoff_actions.append("Repair prior delivery board entries to include prior anchors.")

    if not missing_plan_keys:
        wins.append("Partner outreach dataset is available for launch execution.")
    else:
        misses.append("Partner outreach dataset is missing required keys.")
        handoff_actions.append(
            "Update docs/roadmap/plans/partner-outreach-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            "Partner outreach closeout lane is fully complete and ready for growth campaign priorities."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "partner-outreach-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "scale_upgrade_summary": str(scale_upgrade_summary.relative_to(root))
            if scale_upgrade_summary.exists()
            else str(scale_upgrade_summary),
            "scale_upgrade_delivery_board": str(scale_upgrade_board.relative_to(root))
            if scale_upgrade_board.exists()
            else str(scale_upgrade_board),
            "partner_outreach_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "scale_upgrade_activation_score": scale_upgrade_score,
            "scale_upgrade_checks": scale_upgrade_check_count,
            "scale_upgrade_delivery_board_items": board_count,
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
        "Partner Outreach Closeout summary",
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
        target / "partner-outreach-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "partner-outreach-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "partner-outreach-integration-brief.md", "# Integration brief\n")
    _write(target / "partner-outreach-plan.md", "# Partner outreach plan\n")
    _write(
        target / "partner-outreach-partner-execution-ledger.json",
        json.dumps({"executions": []}, indent=2) + "\n",
    )
    _write(
        target / "partner-outreach-partner-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(target / "partner-outreach-execution-log.md", "# Execution log\n")
    _write(
        target / "partner-outreach-delivery-board.md",
        "\n".join(["# Delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "partner-outreach-validation-commands.md",
        "# Validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "partner-outreach-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_partner_outreach_closeout_summary_impl(root: Path) -> dict[str, Any]:
    """Compatibility alias for legacy builder name."""
    return build_partner_outreach_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Partner Outreach Closeout checks")
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

    payload = build_partner_outreach_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/partner-outreach-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
