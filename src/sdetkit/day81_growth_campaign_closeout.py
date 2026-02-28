from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day81-growth-campaign-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY80_SUMMARY_PATH = "docs/artifacts/day80-partner-outreach-closeout-pack/day80-partner-outreach-closeout-summary.json"
_DAY80_BOARD_PATH = "docs/artifacts/day80-partner-outreach-closeout-pack/day80-delivery-board.md"
_PLAN_PATH = ".day81-growth-campaign-plan.json"
_SECTION_HEADER = "# Day 81 \u2014 Growth campaign closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 81 matters",
    "## Required inputs (Day 80)",
    "## Day 81 command lane",
    "## Growth campaign contract",
    "## Growth campaign quality checklist",
    "## Day 81 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day81-growth-campaign-closeout --format json --strict",
    "python -m sdetkit day81-growth-campaign-closeout --emit-pack-dir docs/artifacts/day81-growth-campaign-closeout-pack --format json --strict",
    "python -m sdetkit day81-growth-campaign-closeout --execute --evidence-dir docs/artifacts/day81-growth-campaign-closeout-pack/evidence --format json --strict",
    "python scripts/check_day81_growth_campaign_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day81-growth-campaign-closeout --format json --strict",
    "python -m sdetkit day81-growth-campaign-closeout --emit-pack-dir docs/artifacts/day81-growth-campaign-closeout-pack --format json --strict",
    "python scripts/check_day81_growth_campaign_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 81 growth campaign execution and signoff.",
    "The Day 81 lane references Day 80 outcomes, controls, and KPI continuity signals.",
    "Every Day 81 section includes campaign CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 81 closeout records campaign outcomes, confidence notes, and Day 82 execution priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes campaign baseline, audience assumptions, and launch cadence",
    "- [ ] Every campaign lane row has owner, execution window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures campaign score delta, partner carryover delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, campaign plan, execution ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 81 integration brief committed",
    "- [ ] Day 81 growth campaign plan committed",
    "- [ ] Day 81 campaign execution ledger exported",
    "- [ ] Day 81 campaign KPI scorecard snapshot exported",
    "- [ ] Day 82 execution priorities drafted from Day 81 learnings",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"campaign_tracks"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DAY81_DEFAULT_PAGE = """# Day 81 \u2014 Growth campaign closeout lane

Day 81 closes with a major upgrade that converts Day 80 partner outreach outcomes into a growth-campaign execution pack.

## Why Day 81 matters

- Turns Day 80 partner outreach outcomes into growth campaign execution proof across docs, rollout, and demand loops.
- Protects launch quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.
- Creates a deterministic handoff from Day 81 growth campaign closeout into Day 82 execution priorities.

## Required inputs (Day 80)

- `docs/artifacts/day80-partner-outreach-closeout-pack/day80-partner-outreach-closeout-summary.json`
- `docs/artifacts/day80-partner-outreach-closeout-pack/day80-delivery-board.md`
- `.day81-growth-campaign-plan.json`

## Day 81 command lane

```bash
python -m sdetkit day81-growth-campaign-closeout --format json --strict
python -m sdetkit day81-growth-campaign-closeout --emit-pack-dir docs/artifacts/day81-growth-campaign-closeout-pack --format json --strict
python -m sdetkit day81-growth-campaign-closeout --execute --evidence-dir docs/artifacts/day81-growth-campaign-closeout-pack/evidence --format json --strict
python scripts/check_day81_growth_campaign_closeout_contract.py
```

## Growth campaign contract

- Single owner + backup reviewer are assigned for Day 81 growth campaign execution and signoff.
- The Day 81 lane references Day 80 outcomes, controls, and KPI continuity signals.
- Every Day 81 section includes campaign CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 81 closeout records campaign outcomes, confidence notes, and Day 82 execution priorities.

## Growth campaign quality checklist

- [ ] Includes campaign baseline, audience assumptions, and launch cadence
- [ ] Every campaign lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures campaign score delta, partner carryover delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, campaign plan, execution ledger, KPI scorecard, and execution log

## Day 81 delivery board

- [ ] Day 81 integration brief committed
- [ ] Day 81 growth campaign plan committed
- [ ] Day 81 campaign execution ledger exported
- [ ] Day 81 campaign KPI scorecard snapshot exported
- [ ] Day 82 execution priorities drafted from Day 81 learnings

## Scoring model

Day 81 weighted score (0-100):

- Contract + command lane integrity (35)
- Day 80 continuity baseline quality (35)
- Campaign evidence data + delivery board completeness (30)
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


def _checklist_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip().startswith("- ["))


def build_day81_growth_campaign_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read_text(root / "README.md")
    docs_index_text = _read_text(root / "docs/index.md")
    page_text = _read_text(root / _PAGE_PATH)
    top10_text = _read_text(root / _TOP10_PATH)

    day80_summary = root / _DAY80_SUMMARY_PATH
    day80_board = root / _DAY80_BOARD_PATH
    day80_payload = _load_json(day80_summary)
    day80_score = int(day80_payload.get("summary", {}).get("activation_score", 0) or 0)
    day80_strict = bool(day80_payload.get("summary", {}).get("strict_pass", False))
    day80_check_count = len(day80_payload.get("checks", []))

    board_text = _read_text(day80_board)
    board_count = _checklist_count(board_text)
    board_has_day80 = "Day 80" in board_text

    missing_sections = [section for section in _REQUIRED_SECTIONS if section not in page_text]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]
    missing_contract_lines = [line for line in _REQUIRED_CONTRACT_LINES if line not in page_text]
    missing_quality_lines = [line for line in _REQUIRED_QUALITY_LINES if line not in page_text]
    missing_board_items = [item for item in _REQUIRED_DELIVERY_BOARD_LINES if item not in page_text]

    plan_text = _read_text(root / _PLAN_PATH)
    missing_plan_keys = [key for key in _REQUIRED_DATA_KEYS if key not in plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day81_command",
            "weight": 7,
            "passed": ("day81-growth-campaign-closeout" in readme_text),
            "evidence": "README day81 command lane",
        },
        {
            "check_id": "docs_index_day81_links",
            "weight": 8,
            "passed": (
                "day-81-big-upgrade-report.md" in docs_index_text
                and "integrations-day81-growth-campaign-closeout.md" in docs_index_text
            ),
            "evidence": "day-81-big-upgrade-report.md + integrations-day81-growth-campaign-closeout.md",
        },
        {
            "check_id": "top10_day81_alignment",
            "weight": 5,
            "passed": ("Day 80" in top10_text and "Day 81" in top10_text),
            "evidence": "Day 80 + Day 81 strategy chain",
        },
        {
            "check_id": "day80_summary_present",
            "weight": 10,
            "passed": day80_summary.exists(),
            "evidence": str(day80_summary),
        },
        {
            "check_id": "day80_delivery_board_present",
            "weight": 7,
            "passed": day80_board.exists(),
            "evidence": str(day80_board),
        },
        {
            "check_id": "day80_quality_floor",
            "weight": 13,
            "passed": day80_score >= 85,
            "evidence": {
                "day80_score": day80_score,
                "strict_pass": day80_strict,
                "day80_checks": day80_check_count,
            },
        },
        {
            "check_id": "day80_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day80,
            "evidence": {"board_items": board_count, "contains_day80": board_has_day80},
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
    if not day80_summary.exists() or not day80_board.exists():
        critical_failures.append("day80_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day80_score >= 85:
        wins.append(f"Day 80 continuity baseline is stable with activation score={day80_score}.")
    else:
        misses.append("Day 80 continuity baseline is below the floor (<85).")
        handoff_actions.append(
            "Re-run Day 80 closeout command and raise baseline quality above 85 before Day 81 lock."
        )

    if board_count >= 5 and board_has_day80:
        wins.append(
            f"Day 80 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 80 delivery board integrity is incomplete (needs >=5 items and Day 80 anchors)."
        )
        handoff_actions.append("Repair Day 80 delivery board entries to include Day 80 anchors.")

    if not missing_plan_keys:
        wins.append("Day 81 growth campaign dataset is available for launch execution.")
    else:
        misses.append("Day 81 growth campaign dataset is missing required keys.")
        handoff_actions.append("Update .day81-growth-campaign-plan.json to restore required keys.")

    if not failed and not critical_failures:
        wins.append(
            "Day 81 growth campaign closeout lane is fully complete and ready for Day 82 execution priorities."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day81-growth-campaign-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day80_summary": str(day80_summary.relative_to(root))
            if day80_summary.exists()
            else str(day80_summary),
            "day80_delivery_board": str(day80_board.relative_to(root))
            if day80_board.exists()
            else str(day80_board),
            "growth_campaign_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "day80_activation_score": day80_score,
            "day80_checks": day80_check_count,
            "day80_delivery_board_items": board_count,
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
        "Day 81 growth campaign closeout summary",
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
        target / "day81-growth-campaign-closeout-summary.json", json.dumps(payload, indent=2) + "\n"
    )
    _write(target / "day81-growth-campaign-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day81-integration-brief.md", "# Day 81 integration brief\n")
    _write(target / "day81-growth-campaign-plan.md", "# Day 81 growth campaign plan\n")
    _write(
        target / "day81-campaign-execution-ledger.json",
        json.dumps({"executions": []}, indent=2) + "\n",
    )
    _write(target / "day81-campaign-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day81-execution-log.md", "# Day 81 execution log\n")
    _write(
        target / "day81-delivery-board.md",
        "\n".join(["# Day 81 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day81-validation-commands.md",
        "# Day 81 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day81-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 81 growth campaign closeout checks")
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
        _write(root / _PAGE_PATH, _DAY81_DEFAULT_PAGE)

    payload = build_day81_growth_campaign_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day81-growth-campaign-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
