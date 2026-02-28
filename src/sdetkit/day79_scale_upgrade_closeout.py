from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day79-scale-upgrade-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY78_SUMMARY_PATH = "docs/artifacts/day78-ecosystem-priorities-closeout-pack/day78-ecosystem-priorities-closeout-summary.json"
_DAY78_BOARD_PATH = (
    "docs/artifacts/day78-ecosystem-priorities-closeout-pack/day78-delivery-board.md"
)
_PLAN_PATH = ".day79-scale-upgrade-plan.json"
_SECTION_HEADER = "# Day 79 \u2014 Scale upgrade closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 79 matters",
    "## Required inputs (Day 78)",
    "## Day 79 command lane",
    "## Scale upgrade contract",
    "## Scale upgrade quality checklist",
    "## Day 79 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day79-scale-upgrade-closeout --format json --strict",
    "python -m sdetkit day79-scale-upgrade-closeout --emit-pack-dir docs/artifacts/day79-scale-upgrade-closeout-pack --format json --strict",
    "python -m sdetkit day79-scale-upgrade-closeout --execute --evidence-dir docs/artifacts/day79-scale-upgrade-closeout-pack/evidence --format json --strict",
    "python scripts/check_day79_scale_upgrade_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day79-scale-upgrade-closeout --format json --strict",
    "python -m sdetkit day79-scale-upgrade-closeout --emit-pack-dir docs/artifacts/day79-scale-upgrade-closeout-pack --format json --strict",
    "python scripts/check_day79_scale_upgrade_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 79 scale upgrade execution and signoff.",
    "The Day 79 lane references Day 78 outcomes, controls, and KPI continuity signals.",
    "Every Day 79 section includes enterprise CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 79 closeout records enterprise onboarding outcomes, confidence notes, and Day 80 partner outreach priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes enterprise onboarding baseline, role coverage cadence, and stakeholder assumptions",
    "- [ ] Every scale lane row has owner, execution window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures scale score delta, ecosystem carryover delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, scale upgrade plan, execution ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 79 integration brief committed",
    "- [ ] Day 79 scale upgrade plan committed",
    "- [ ] Day 79 enterprise execution ledger exported",
    "- [ ] Day 79 enterprise KPI scorecard snapshot exported",
    "- [ ] Day 80 partner outreach priorities drafted from Day 79 learnings",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"scale_tracks"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DAY79_DEFAULT_PAGE = """# Day 79 \u2014 Scale upgrade closeout lane

Day 79 closes with a major upgrade that converts Day 78 ecosystem priorities into an enterprise-scale onboarding execution pack.

## Why Day 79 matters

- Turns Day 78 ecosystem priorities into enterprise onboarding readiness proof across docs, rollout, and adoption loops.
- Protects scale quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.
- Creates a deterministic handoff from Day 79 scale upgrades into Day 80 partner outreach priorities.

## Required inputs (Day 78)

- `docs/artifacts/day78-ecosystem-priorities-closeout-pack/day78-ecosystem-priorities-closeout-summary.json`
- `docs/artifacts/day78-ecosystem-priorities-closeout-pack/day78-delivery-board.md`
- `.day79-scale-upgrade-plan.json`

## Day 79 command lane

```bash
python -m sdetkit day79-scale-upgrade-closeout --format json --strict
python -m sdetkit day79-scale-upgrade-closeout --emit-pack-dir docs/artifacts/day79-scale-upgrade-closeout-pack --format json --strict
python -m sdetkit day79-scale-upgrade-closeout --execute --evidence-dir docs/artifacts/day79-scale-upgrade-closeout-pack/evidence --format json --strict
python scripts/check_day79_scale_upgrade_closeout_contract.py
```

## Scale upgrade contract

- Single owner + backup reviewer are assigned for Day 79 scale upgrade execution and signoff.
- The Day 79 lane references Day 78 outcomes, controls, and KPI continuity signals.
- Every Day 79 section includes enterprise CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 79 closeout records enterprise onboarding outcomes, confidence notes, and Day 80 partner outreach priorities.

## Scale upgrade quality checklist

- [ ] Includes enterprise onboarding baseline, role coverage cadence, and stakeholder assumptions
- [ ] Every scale lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures scale score delta, ecosystem carryover delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, scale upgrade plan, execution ledger, KPI scorecard, and execution log

## Day 79 delivery board

- [ ] Day 79 integration brief committed
- [ ] Day 79 scale upgrade plan committed
- [ ] Day 79 enterprise execution ledger exported
- [ ] Day 79 enterprise KPI scorecard snapshot exported
- [ ] Day 80 partner outreach priorities drafted from Day 79 learnings

## Scoring model

Day 79 weighted score (0-100):

- Contract + command lane integrity (35)
- Day 78 continuity baseline quality (35)
- Scale evidence data + delivery board completeness (30)
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
    except Exception:
        return {}


def build_day79_scale_upgrade_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read_text(root / "README.md")
    docs_index_text = _read_text(root / "docs/index.md")
    page_text = _read_text(root / _PAGE_PATH)
    top10_text = _read_text(root / _TOP10_PATH)

    day78_summary = root / _DAY78_SUMMARY_PATH
    day78_board = root / _DAY78_BOARD_PATH
    plan_path = root / _PLAN_PATH

    day78_payload = _load_json(day78_summary)
    day78_score = int(day78_payload.get("summary", {}).get("activation_score", 0) or 0)
    day78_strict = bool(day78_payload.get("summary", {}).get("strict_pass", False))
    day78_check_count = len(day78_payload.get("checks", []))

    board_text = _read_text(day78_board)
    board_count = sum(1 for line in board_text.splitlines() if line.strip().startswith("- [ ]"))
    board_has_day78 = "Day 78" in board_text

    plan_text = _read_text(plan_path)

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_plan_keys = [x for x in _REQUIRED_DATA_KEYS if x not in plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day79_command",
            "weight": 7,
            "passed": ("day79-scale-upgrade-closeout" in readme_text),
            "evidence": "README day79 command lane",
        },
        {
            "check_id": "docs_index_day79_links",
            "weight": 8,
            "passed": (
                "day-79-big-upgrade-report.md" in docs_index_text
                and "integrations-day79-scale-upgrade-closeout.md" in docs_index_text
            ),
            "evidence": "day-79-big-upgrade-report.md + integrations-day79-scale-upgrade-closeout.md",
        },
        {
            "check_id": "top10_day79_alignment",
            "weight": 5,
            "passed": ("Day 78" in top10_text and "Day 79" in top10_text),
            "evidence": "Day 78 + Day 79 strategy chain",
        },
        {
            "check_id": "day78_summary_present",
            "weight": 10,
            "passed": day78_summary.exists(),
            "evidence": str(day78_summary),
        },
        {
            "check_id": "day78_delivery_board_present",
            "weight": 7,
            "passed": day78_board.exists(),
            "evidence": str(day78_board),
        },
        {
            "check_id": "day78_quality_floor",
            "weight": 13,
            "passed": day78_score >= 85,
            "evidence": {
                "day78_score": day78_score,
                "strict_pass": day78_strict,
                "day78_checks": day78_check_count,
            },
        },
        {
            "check_id": "day78_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day78,
            "evidence": {"board_items": board_count, "contains_day78": board_has_day78},
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
    if not day78_summary.exists() or not day78_board.exists():
        critical_failures.append("day78_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day78_score >= 85:
        wins.append(f"Day 78 continuity baseline is stable with activation score={day78_score}.")
    else:
        misses.append("Day 78 continuity baseline is below the floor (<85).")
        handoff_actions.append(
            "Re-run Day 78 closeout command and raise baseline quality above 85 before Day 79 lock."
        )

    if board_count >= 5 and board_has_day78:
        wins.append(
            f"Day 78 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 78 delivery board integrity is incomplete (needs >=5 items and Day 78 anchors)."
        )
        handoff_actions.append("Repair Day 78 delivery board entries to include Day 78 anchors.")

    if not missing_plan_keys:
        wins.append("Day 79 scale upgrade dataset is available for launch execution.")
    else:
        misses.append("Day 79 scale upgrade dataset is missing required keys.")
        handoff_actions.append("Update .day79-scale-upgrade-plan.json to restore required keys.")

    if not failed and not critical_failures:
        wins.append(
            "Day 79 scale upgrade closeout lane is fully complete and ready for Day 80 partner outreach priorities."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day79-scale-upgrade-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day78_summary": str(day78_summary.relative_to(root))
            if day78_summary.exists()
            else str(day78_summary),
            "day78_delivery_board": str(day78_board.relative_to(root))
            if day78_board.exists()
            else str(day78_board),
            "scale_upgrade_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "day78_activation_score": day78_score,
            "day78_checks": day78_check_count,
            "day78_delivery_board_items": board_count,
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
        "Day 79 scale upgrade closeout summary",
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
        target / "day79-scale-upgrade-closeout-summary.json", json.dumps(payload, indent=2) + "\n"
    )
    _write(target / "day79-scale-upgrade-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day79-integration-brief.md", "# Day 79 integration brief\n")
    _write(target / "day79-scale-upgrade-plan.md", "# Day 79 scale upgrade plan\n")
    _write(
        target / "day79-enterprise-execution-ledger.json",
        json.dumps({"executions": []}, indent=2) + "\n",
    )
    _write(
        target / "day79-enterprise-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n"
    )
    _write(target / "day79-execution-log.md", "# Day 79 execution log\n")
    _write(
        target / "day79-delivery-board.md",
        "\n".join(["# Day 79 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day79-validation-commands.md",
        "# Day 79 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day79-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 79 scale upgrade closeout checks")
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
        _write(root / _PAGE_PATH, _DAY79_DEFAULT_PAGE)

    payload = build_day79_scale_upgrade_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day79-scale-upgrade-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
