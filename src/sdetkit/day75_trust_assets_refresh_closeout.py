from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day75-trust-assets-refresh-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY74_SUMMARY_PATH = "docs/artifacts/day74-distribution-scaling-closeout-pack/day74-distribution-scaling-closeout-summary.json"
_DAY74_BOARD_PATH = (
    "docs/artifacts/day74-distribution-scaling-closeout-pack/day74-delivery-board.md"
)
_TRUST_PLAN_PATH = ".day75-trust-assets-refresh-plan.json"
_SECTION_HEADER = "# Day 75 — Trust assets refresh closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 75 matters",
    "## Required inputs (Day 74)",
    "## Day 75 command lane",
    "## Trust assets refresh contract",
    "## Trust refresh quality checklist",
    "## Day 75 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day75-trust-assets-refresh-closeout --format json --strict",
    "python -m sdetkit day75-trust-assets-refresh-closeout --emit-pack-dir docs/artifacts/day75-trust-assets-refresh-closeout-pack --format json --strict",
    "python -m sdetkit day75-trust-assets-refresh-closeout --execute --evidence-dir docs/artifacts/day75-trust-assets-refresh-closeout-pack/evidence --format json --strict",
    "python scripts/check_day75_trust_assets_refresh_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day75-trust-assets-refresh-closeout --format json --strict",
    "python -m sdetkit day75-trust-assets-refresh-closeout --emit-pack-dir docs/artifacts/day75-trust-assets-refresh-closeout-pack --format json --strict",
    "python scripts/check_day75_trust_assets_refresh_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 75 trust assets refresh execution and signoff.",
    "The Day 75 lane references Day 74 outcomes, controls, and KPI continuity signals.",
    "Every Day 75 section includes trust-surface CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 75 closeout records trust outcomes, confidence notes, and Day 76 contributor-recognition priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes trust-surface baseline, proof-link cadence, and stakeholder assumptions",
    "- [ ] Every trust lane row has owner, refresh window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures trust score delta, governance proof coverage delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, trust refresh plan, controls log, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 75 integration brief committed",
    "- [ ] Day 75 trust assets refresh plan committed",
    "- [ ] Day 75 trust controls and assumptions log exported",
    "- [ ] Day 75 trust KPI scorecard snapshot exported",
    "- [ ] Day 76 contributor-recognition priorities drafted from Day 75 learnings",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"trust_surfaces"',
    '"baseline"',
    '"target"',
    '"confidence"',
    '"owner"',
]

_DAY75_DEFAULT_PAGE = """# Day 75 — Trust assets refresh closeout lane

Day 75 closes with a major upgrade that turns Day 74 distribution outcomes into a governance-grade trust refresh execution pack.

## Why Day 75 matters

- Converts Day 74 scaling proof into trust-surface upgrades across security, governance, and reliability docs.
- Protects trust quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.
- Creates a deterministic handoff from Day 75 trust refresh execution into Day 76 contributor recognition.

## Required inputs (Day 74)

- `docs/artifacts/day74-distribution-scaling-closeout-pack/day74-distribution-scaling-closeout-summary.json`
- `docs/artifacts/day74-distribution-scaling-closeout-pack/day74-delivery-board.md`
- `.day75-trust-assets-refresh-plan.json`

## Day 75 command lane

```bash
python -m sdetkit day75-trust-assets-refresh-closeout --format json --strict
python -m sdetkit day75-trust-assets-refresh-closeout --emit-pack-dir docs/artifacts/day75-trust-assets-refresh-closeout-pack --format json --strict
python -m sdetkit day75-trust-assets-refresh-closeout --execute --evidence-dir docs/artifacts/day75-trust-assets-refresh-closeout-pack/evidence --format json --strict
python scripts/check_day75_trust_assets_refresh_closeout_contract.py
```

## Trust assets refresh contract

- Single owner + backup reviewer are assigned for Day 75 trust assets refresh execution and signoff.
- The Day 75 lane references Day 74 outcomes, controls, and KPI continuity signals.
- Every Day 75 section includes trust-surface CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 75 closeout records trust outcomes, confidence notes, and Day 76 contributor-recognition priorities.

## Trust refresh quality checklist

- [ ] Includes trust-surface baseline, proof-link cadence, and stakeholder assumptions
- [ ] Every trust lane row has owner, refresh window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures trust score delta, governance proof coverage delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, trust refresh plan, controls log, KPI scorecard, and execution log

## Day 75 delivery board

- [ ] Day 75 integration brief committed
- [ ] Day 75 trust assets refresh plan committed
- [ ] Day 75 trust controls and assumptions log exported
- [ ] Day 75 trust KPI scorecard snapshot exported
- [ ] Day 76 contributor-recognition priorities drafted from Day 75 learnings

## Scoring model

Day 75 weighted score (0-100):

- Contract + command lane integrity (35)
- Day 74 continuity baseline quality (35)
- Trust evidence data + delivery board completeness (30)

Strict pass requires score >= 95 and zero critical failures.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_day74(summary_path: Path) -> tuple[int, bool, int]:
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


def build_day75_trust_assets_refresh_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    trust_plan_text = _read(root / _TRUST_PLAN_PATH)

    day74_summary = root / _DAY74_SUMMARY_PATH
    day74_board = root / _DAY74_BOARD_PATH
    day74_score, day74_strict, day74_check_count = _load_day74(day74_summary)
    board_count, board_has_day74 = _count_board_items(day74_board, "Day 74")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_plan_keys = [x for x in _REQUIRED_DATA_KEYS if x not in trust_plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day75_command",
            "weight": 7,
            "passed": ("day75-trust-assets-refresh-closeout" in readme_text),
            "evidence": "README day75 command lane",
        },
        {
            "check_id": "docs_index_day75_links",
            "weight": 8,
            "passed": (
                "day-75-big-upgrade-report.md" in docs_index_text
                and "integrations-day75-trust-assets-refresh-closeout.md" in docs_index_text
            ),
            "evidence": "day-75-big-upgrade-report.md + integrations-day75-trust-assets-refresh-closeout.md",
        },
        {
            "check_id": "top10_day75_alignment",
            "weight": 5,
            "passed": ("Day 75" in top10_text and "Day 76" in top10_text),
            "evidence": "Day 75 + Day 76 strategy chain",
        },
        {
            "check_id": "day74_summary_present",
            "weight": 10,
            "passed": day74_summary.exists(),
            "evidence": str(day74_summary),
        },
        {
            "check_id": "day74_delivery_board_present",
            "weight": 7,
            "passed": day74_board.exists(),
            "evidence": str(day74_board),
        },
        {
            "check_id": "day74_quality_floor",
            "weight": 13,
            "passed": day74_strict and day74_score >= 95,
            "evidence": {
                "day74_score": day74_score,
                "strict_pass": day74_strict,
                "day74_checks": day74_check_count,
            },
        },
        {
            "check_id": "day74_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day74,
            "evidence": {"board_items": board_count, "contains_day74": board_has_day74},
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
            "check_id": "trust_refresh_plan_data_present",
            "weight": 10,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _TRUST_PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day74_summary.exists() or not day74_board.exists():
        critical_failures.append("day74_handoff_inputs")
    if not day74_strict:
        critical_failures.append("day74_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day74_strict:
        wins.append(f"Day 74 continuity is strict-pass with activation score={day74_score}.")
    else:
        misses.append("Day 74 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 74 closeout command and restore strict baseline before Day 75 lock."
        )

    if board_count >= 5 and board_has_day74:
        wins.append(
            f"Day 74 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 74 delivery board integrity is incomplete (needs >=5 items and Day 74 anchors)."
        )
        handoff_actions.append("Repair Day 74 delivery board entries to include Day 74 anchors.")

    if not missing_plan_keys:
        wins.append("Day 75 trust assets refresh dataset is available for launch execution.")
    else:
        misses.append("Day 75 trust assets refresh dataset is missing required keys.")
        handoff_actions.append(
            "Update .day75-trust-assets-refresh-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 75 trust assets refresh closeout lane is fully complete and ready for Day 76 contributor recognition."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day75-trust-assets-refresh-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day74_summary": str(day74_summary.relative_to(root))
            if day74_summary.exists()
            else str(day74_summary),
            "day74_delivery_board": str(day74_board.relative_to(root))
            if day74_board.exists()
            else str(day74_board),
            "trust_refresh_plan": _TRUST_PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "day74_activation_score": day74_score,
            "day74_checks": day74_check_count,
            "day74_delivery_board_items": board_count,
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
        "Day 75 trust assets refresh closeout summary",
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
        target / "day75-trust-assets-refresh-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "day75-trust-assets-refresh-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day75-integration-brief.md", "# Day 75 integration brief\n")
    _write(target / "day75-trust-assets-refresh-plan.md", "# Day 75 trust assets refresh plan\n")
    _write(target / "day75-trust-controls-log.json", json.dumps({"controls": []}, indent=2) + "\n")
    _write(target / "day75-trust-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day75-execution-log.md", "# Day 75 execution log\n")
    _write(
        target / "day75-delivery-board.md",
        "\n".join(["# Day 75 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day75-validation-commands.md",
        "# Day 75 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    events: list[dict[str, Any]] = []
    out_dir = evidence_dir if evidence_dir.is_absolute() else root / evidence_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, command in enumerate(_EXECUTION_COMMANDS, start=1):
        result = subprocess.run(shlex.split(command), cwd=root, capture_output=True, text=True)
        event = {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        events.append(event)
        _write(out_dir / f"command-{idx:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        out_dir / "day75-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 75 trust assets refresh closeout checks")
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
        _write(root / _PAGE_PATH, _DAY75_DEFAULT_PAGE)

    payload = build_day75_trust_assets_refresh_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day75-trust-assets-refresh-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
