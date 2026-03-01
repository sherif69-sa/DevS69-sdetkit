from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day78-ecosystem-priorities-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY77_SUMMARY_PATH = "docs/artifacts/day77-community-touchpoint-closeout-pack/day77-community-touchpoint-closeout-summary.json"
_DAY77_BOARD_PATH = (
    "docs/artifacts/day77-community-touchpoint-closeout-pack/day77-delivery-board.md"
)
_PLAN_PATH = "docs/roadmap/plans/day78-ecosystem-priorities-plan.json"
_SECTION_HEADER = "# Day 78 \u2014 Ecosystem priorities closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 78 matters",
    "## Required inputs (Day 77)",
    "## Day 78 command lane",
    "## Ecosystem priorities contract",
    "## Ecosystem priorities quality checklist",
    "## Day 78 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day78-ecosystem-priorities-closeout --format json --strict",
    "python -m sdetkit day78-ecosystem-priorities-closeout --emit-pack-dir docs/artifacts/day78-ecosystem-priorities-closeout-pack --format json --strict",
    "python -m sdetkit day78-ecosystem-priorities-closeout --execute --evidence-dir docs/artifacts/day78-ecosystem-priorities-closeout-pack/evidence --format json --strict",
    "python scripts/check_day78_ecosystem_priorities_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day78-ecosystem-priorities-closeout --format json --strict",
    "python -m sdetkit day78-ecosystem-priorities-closeout --emit-pack-dir docs/artifacts/day78-ecosystem-priorities-closeout-pack --format json --strict",
    "python scripts/check_day78_ecosystem_priorities_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 78 ecosystem priorities execution and signoff.",
    "The Day 78 lane references Day 77 outcomes, controls, and KPI continuity signals.",
    "Every Day 78 section includes ecosystem CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 78 closeout records ecosystem outcomes, confidence notes, and Day 79 scale priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes ecosystem baseline, priority cadence, and stakeholder assumptions",
    "- [ ] Every ecosystem lane row has owner, workstream window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures ecosystem score delta, touchpoint carryover delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, ecosystem priorities plan, workstream ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 78 integration brief committed",
    "- [ ] Day 78 ecosystem priorities plan committed",
    "- [ ] Day 78 ecosystem workstream ledger exported",
    "- [ ] Day 78 ecosystem KPI scorecard snapshot exported",
    "- [ ] Day 79 scale priorities drafted from Day 78 learnings",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"ecosystem_tracks"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DAY78_DEFAULT_PAGE = """# Day 78 \u2014 Ecosystem priorities closeout lane

Day 78 closes with a major upgrade that converts Day 77 community-touchpoint outcomes into an ecosystem-priorities execution pack.

## Why Day 78 matters

- Turns Day 77 community-touchpoint outcomes into ecosystem-facing expansion proof across docs, governance, and release channels.
- Protects launch quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.
- Creates a deterministic handoff from Day 78 ecosystem priorities into Day 79 scale priorities.

## Required inputs (Day 77)

- `docs/artifacts/day77-community-touchpoint-closeout-pack/day77-community-touchpoint-closeout-summary.json`
- `docs/artifacts/day77-community-touchpoint-closeout-pack/day77-delivery-board.md`
- `docs/roadmap/plans/day78-ecosystem-priorities-plan.json`

## Day 78 command lane

```bash
python -m sdetkit day78-ecosystem-priorities-closeout --format json --strict
python -m sdetkit day78-ecosystem-priorities-closeout --emit-pack-dir docs/artifacts/day78-ecosystem-priorities-closeout-pack --format json --strict
python -m sdetkit day78-ecosystem-priorities-closeout --execute --evidence-dir docs/artifacts/day78-ecosystem-priorities-closeout-pack/evidence --format json --strict
python scripts/check_day78_ecosystem_priorities_closeout_contract.py
```

## Ecosystem priorities contract

- Single owner + backup reviewer are assigned for Day 78 ecosystem priorities execution and signoff.
- The Day 78 lane references Day 77 outcomes, controls, and KPI continuity signals.
- Every Day 78 section includes ecosystem CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 78 closeout records ecosystem outcomes, confidence notes, and Day 79 scale priorities.

## Ecosystem priorities quality checklist

- [ ] Includes ecosystem baseline, priority cadence, and stakeholder assumptions
- [ ] Every ecosystem lane row has owner, workstream window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures ecosystem score delta, touchpoint carryover delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, ecosystem priorities plan, workstream ledger, KPI scorecard, and execution log

## Day 78 delivery board

- [ ] Day 78 integration brief committed
- [ ] Day 78 ecosystem priorities plan committed
- [ ] Day 78 ecosystem workstream ledger exported
- [ ] Day 78 ecosystem KPI scorecard snapshot exported
- [ ] Day 79 scale priorities drafted from Day 78 learnings

## Scoring model

Day 78 weighted score (0-100):

- Contract + command lane integrity (35)
- Day 77 continuity baseline quality (35)
- Ecosystem evidence data + delivery board completeness (30)

Strict pass requires score >= 95 and zero critical failures.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_day77(summary_path: Path) -> tuple[int, bool, int]:
    if not summary_path.exists():
        return 0, False, 0
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    checks = data.get("checks", [])
    return (
        int(summary.get("activation_score", 0)),
        bool(summary.get("strict_pass", False)),
        len(checks),
    )


def _count_board_items(board_path: Path, anchor: str) -> tuple[int, bool]:
    if not board_path.exists():
        return 0, False
    text = board_path.read_text(encoding="utf-8")
    items = [line for line in text.splitlines() if line.strip().startswith("- [")]
    return len(items), (anchor in text)


def build_day78_ecosystem_priorities_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    plan_text = _read(root / _PLAN_PATH)

    day77_summary = root / _DAY77_SUMMARY_PATH
    day77_board = root / _DAY77_BOARD_PATH
    day77_score, day77_strict, day77_check_count = _load_day77(day77_summary)
    board_count, board_has_day77 = _count_board_items(day77_board, "Day 77")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_plan_keys = [x for x in _REQUIRED_DATA_KEYS if x not in plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day78_command",
            "weight": 7,
            "passed": ("day78-ecosystem-priorities-closeout" in readme_text),
            "evidence": "README day78 command lane",
        },
        {
            "check_id": "docs_index_day78_links",
            "weight": 8,
            "passed": (
                "day-78-big-upgrade-report.md" in docs_index_text
                and "integrations-day78-ecosystem-priorities-closeout.md" in docs_index_text
            ),
            "evidence": "day-78-big-upgrade-report.md + integrations-day78-ecosystem-priorities-closeout.md",
        },
        {
            "check_id": "top10_day78_alignment",
            "weight": 5,
            "passed": ("Day 77" in top10_text and "Day 78" in top10_text),
            "evidence": "Day 77 + Day 78 strategy chain",
        },
        {
            "check_id": "day77_summary_present",
            "weight": 10,
            "passed": day77_summary.exists(),
            "evidence": str(day77_summary),
        },
        {
            "check_id": "day77_delivery_board_present",
            "weight": 7,
            "passed": day77_board.exists(),
            "evidence": str(day77_board),
        },
        {
            "check_id": "day77_quality_floor",
            "weight": 13,
            "passed": day77_score >= 85,
            "evidence": {
                "day77_score": day77_score,
                "strict_pass": day77_strict,
                "day77_checks": day77_check_count,
            },
        },
        {
            "check_id": "day77_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day77,
            "evidence": {"board_items": board_count, "contains_day77": board_has_day77},
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
            "check_id": "ecosystem_plan_data_present",
            "weight": 10,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day77_summary.exists() or not day77_board.exists():
        critical_failures.append("day77_handoff_inputs")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day77_score >= 85:
        wins.append(f"Day 77 continuity baseline is stable with activation score={day77_score}.")
    else:
        misses.append("Day 77 continuity baseline is below the floor (<85).")
        handoff_actions.append(
            "Re-run Day 77 closeout command and raise baseline quality above 85 before Day 78 lock."
        )

    if board_count >= 5 and board_has_day77:
        wins.append(
            f"Day 77 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 77 delivery board integrity is incomplete (needs >=5 items and Day 77 anchors)."
        )
        handoff_actions.append("Repair Day 77 delivery board entries to include Day 77 anchors.")

    if not missing_plan_keys:
        wins.append("Day 78 ecosystem priorities dataset is available for launch execution.")
    else:
        misses.append("Day 78 ecosystem priorities dataset is missing required keys.")
        handoff_actions.append(
            "Update docs/roadmap/plans/day78-ecosystem-priorities-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 78 ecosystem priorities closeout lane is fully complete and ready for Day 79 scale priorities."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day78-ecosystem-priorities-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day77_summary": str(day77_summary.relative_to(root))
            if day77_summary.exists()
            else str(day77_summary),
            "day77_delivery_board": str(day77_board.relative_to(root))
            if day77_board.exists()
            else str(day77_board),
            "ecosystem_priorities_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "day77_activation_score": day77_score,
            "day77_checks": day77_check_count,
            "day77_delivery_board_items": board_count,
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
        "Day 78 ecosystem priorities closeout summary",
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
        target / "day78-ecosystem-priorities-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "day78-ecosystem-priorities-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day78-integration-brief.md", "# Day 78 integration brief\n")
    _write(target / "day78-ecosystem-priorities-plan.md", "# Day 78 ecosystem priorities plan\n")
    _write(
        target / "day78-ecosystem-workstream-ledger.json",
        json.dumps({"workstreams": []}, indent=2) + "\n",
    )
    _write(target / "day78-ecosystem-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day78-execution-log.md", "# Day 78 execution log\n")
    _write(
        target / "day78-delivery-board.md",
        "\n".join(["# Day 78 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day78-validation-commands.md",
        "# Day 78 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day78-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 78 ecosystem priorities closeout checks")
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
        _write(root / _PAGE_PATH, _DAY78_DEFAULT_PAGE)

    payload = build_day78_ecosystem_priorities_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day78-ecosystem-priorities-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
