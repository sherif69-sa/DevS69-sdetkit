from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day56-stabilization-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY55_SUMMARY_PATH = "docs/artifacts/day55-contributor-activation-closeout-pack/day55-contributor-activation-closeout-summary.json"
_DAY55_BOARD_PATH = (
    "docs/artifacts/day55-contributor-activation-closeout-pack/day55-delivery-board.md"
)
_SECTION_HEADER = "# Day 56 \u2014 Stabilization closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 56 matters",
    "## Required inputs (Day 55)",
    "## Day 56 command lane",
    "## Stabilization contract",
    "## Stabilization quality checklist",
    "## Day 56 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day56-stabilization-closeout --format json --strict",
    "python -m sdetkit day56-stabilization-closeout --emit-pack-dir docs/artifacts/day56-stabilization-closeout-pack --format json --strict",
    "python -m sdetkit day56-stabilization-closeout --execute --evidence-dir docs/artifacts/day56-stabilization-closeout-pack/evidence --format json --strict",
    "python scripts/check_day56_stabilization_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day56-stabilization-closeout --format json --strict",
    "python -m sdetkit day56-stabilization-closeout --emit-pack-dir docs/artifacts/day56-stabilization-closeout-pack --format json --strict",
    "python scripts/check_day56_stabilization_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 56 stabilization execution and KPI recovery.",
    "The Day 56 lane references Day 55 contributor activation outcomes and unresolved risks.",
    "Every Day 56 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 56 closeout records stabilization outcomes and Day 57 deep-audit priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes bottleneck digest, remediation experiments, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes stabilization brief, risk ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 56 stabilization brief committed",
    "- [ ] Day 56 stabilization plan reviewed with owner + backup",
    "- [ ] Day 56 risk ledger exported",
    "- [ ] Day 56 KPI scorecard snapshot exported",
    "- [ ] Day 57 deep-audit priorities drafted from Day 56 learnings",
]

_DAY56_DEFAULT_PAGE = """# Day 56 \u2014 Stabilization closeout lane

Day 56 closes with a major stabilization upgrade that turns Day 55 contributor-activation outcomes into deterministic KPI recovery and follow-through.

## Why Day 56 matters

- Converts Day 55 contributor outcomes into repeatable stabilization loops.
- Protects quality with ownership, command proof, and KPI rollback guardrails.
- Produces a deterministic handoff from Day 56 closeout into Day 57 deep audit planning.

## Required inputs (Day 55)

- `docs/artifacts/day55-contributor-activation-closeout-pack/day55-contributor-activation-closeout-summary.json`
- `docs/artifacts/day55-contributor-activation-closeout-pack/day55-delivery-board.md`

## Day 56 command lane

```bash
python -m sdetkit day56-stabilization-closeout --format json --strict
python -m sdetkit day56-stabilization-closeout --emit-pack-dir docs/artifacts/day56-stabilization-closeout-pack --format json --strict
python -m sdetkit day56-stabilization-closeout --execute --evidence-dir docs/artifacts/day56-stabilization-closeout-pack/evidence --format json --strict
python scripts/check_day56_stabilization_closeout_contract.py
```

## Stabilization contract

- Single owner + backup reviewer are assigned for Day 56 stabilization execution and KPI recovery.
- The Day 56 lane references Day 55 contributor activation outcomes and unresolved risks.
- Every Day 56 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 56 closeout records stabilization outcomes and Day 57 deep-audit priorities.

## Stabilization quality checklist

- [ ] Includes bottleneck digest, remediation experiments, and rollback strategy
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes stabilization brief, risk ledger, KPI scorecard, and execution log

## Day 56 delivery board

- [ ] Day 56 stabilization brief committed
- [ ] Day 56 stabilization plan reviewed with owner + backup
- [ ] Day 56 risk ledger exported
- [ ] Day 56 KPI scorecard snapshot exported
- [ ] Day 57 deep-audit priorities drafted from Day 56 learnings

## Scoring model

Day 56 weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 55 continuity and strict baseline carryover: 35 points.
- Stabilization contract lock + delivery board readiness: 15 points.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _load_day55(path: Path) -> tuple[int, bool, int]:
    payload_obj = _load_json(path)
    if not isinstance(payload_obj, dict):
        return 0, False, 0
    summary_obj = payload_obj.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    checks_obj = payload_obj.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    return (
        int(summary.get("activation_score", 0)),
        bool(summary.get("strict_pass", False)),
        len(checks),
    )


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def _board_stats(path: Path) -> tuple[int, bool]:
    text = _read(path)
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- [")]
    return len(lines), ("Day 55" in text)


def build_day56_stabilization_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_path = root / _PAGE_PATH
    page_text = _read(page_path)
    top10_text = _read(root / _TOP10_PATH)

    missing_sections = [
        item for item in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if item not in page_text
    ]
    missing_commands = _contains_all_lines(page_text, _REQUIRED_COMMANDS)
    missing_contract_lines = _contains_all_lines(
        page_text, [f"- {line}" for line in _REQUIRED_CONTRACT_LINES]
    )
    missing_quality_lines = _contains_all_lines(page_text, _REQUIRED_QUALITY_LINES)
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    day55_summary = root / _DAY55_SUMMARY_PATH
    day55_board = root / _DAY55_BOARD_PATH
    day55_score, day55_strict, day55_check_count = _load_day55(day55_summary)
    board_count, board_has_day55 = _board_stats(day55_board)

    checks: list[dict[str, Any]] = [
        {
            "check_id": "docs_page_exists",
            "weight": 10,
            "passed": page_path.exists(),
            "evidence": str(page_path),
        },
        {
            "check_id": "required_sections_present",
            "weight": 10,
            "passed": not missing_sections,
            "evidence": {"missing_sections": missing_sections},
        },
        {
            "check_id": "required_commands_present",
            "weight": 10,
            "passed": not missing_commands,
            "evidence": {"missing_commands": missing_commands},
        },
        {
            "check_id": "readme_day56_link",
            "weight": 8,
            "passed": _PAGE_PATH in readme_text,
            "evidence": _PAGE_PATH,
        },
        {
            "check_id": "readme_day56_command",
            "weight": 4,
            "passed": "day56-stabilization-closeout" in readme_text,
            "evidence": "day56-stabilization-closeout",
        },
        {
            "check_id": "docs_index_day56_links",
            "weight": 8,
            "passed": (
                "day-56-big-upgrade-report.md" in docs_index_text
                and "integrations-day56-stabilization-closeout.md" in docs_index_text
            ),
            "evidence": "day-56-big-upgrade-report.md + integrations-day56-stabilization-closeout.md",
        },
        {
            "check_id": "top10_day56_alignment",
            "weight": 5,
            "passed": ("Day 56" in top10_text and "Day 57" in top10_text),
            "evidence": "Day 56 + Day 57 strategy chain",
        },
        {
            "check_id": "day55_summary_present",
            "weight": 10,
            "passed": day55_summary.exists(),
            "evidence": str(day55_summary),
        },
        {
            "check_id": "day55_delivery_board_present",
            "weight": 8,
            "passed": day55_board.exists(),
            "evidence": str(day55_board),
        },
        {
            "check_id": "day55_quality_floor",
            "weight": 10,
            "passed": day55_strict and day55_score >= 95,
            "evidence": {
                "day55_score": day55_score,
                "strict_pass": day55_strict,
                "day55_checks": day55_check_count,
            },
        },
        {
            "check_id": "day55_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day55,
            "evidence": {"board_items": board_count, "contains_day55": board_has_day55},
        },
        {
            "check_id": "stabilization_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "stabilization_quality_checklist_locked",
            "weight": 3,
            "passed": not missing_quality_lines,
            "evidence": {"missing_quality_items": missing_quality_lines},
        },
        {
            "check_id": "delivery_board_locked",
            "weight": 2,
            "passed": not missing_board_items,
            "evidence": {"missing_board_items": missing_board_items},
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day55_summary.exists() or not day55_board.exists():
        critical_failures.append("day55_handoff_inputs")
    if not day55_strict:
        critical_failures.append("day55_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day55_strict:
        wins.append(f"Day 55 continuity is strict-pass with activation score={day55_score}.")
    else:
        misses.append("Day 55 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 55 contributor activation closeout command and restore strict baseline before Day 56 lock."
        )

    if board_count >= 5 and board_has_day55:
        wins.append(
            f"Day 55 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 55 delivery board integrity is incomplete (needs >=5 items and Day 55 anchors)."
        )
        handoff_actions.append("Repair Day 55 delivery board entries to include Day 55 anchors.")

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Stabilization contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Stabilization contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 56 contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 56 stabilization closeout lane is fully complete and ready for Day 57 deep audit lane."
        )

    score = int(round(sum(c["weight"] for c in checks if bool(c["passed"]))))
    return {
        "name": "day56-stabilization-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day55_summary": str(day55_summary.relative_to(root))
            if day55_summary.exists()
            else str(day55_summary),
            "day55_delivery_board": str(day55_board.relative_to(root))
            if day55_board.exists()
            else str(day55_board),
        },
        "checks": checks,
        "rollup": {
            "day55_activation_score": day55_score,
            "day55_checks": day55_check_count,
            "day55_delivery_board_items": board_count,
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
        "Day 56 stabilization closeout summary",
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
        target / "day56-stabilization-closeout-summary.json", json.dumps(payload, indent=2) + "\n"
    )
    _write(target / "day56-stabilization-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day56-stabilization-brief.md", "# Day 56 stabilization brief\n")
    _write(target / "day56-risk-ledger.csv", "risk,owner,mitigation,status\n")
    _write(
        target / "day56-stabilization-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n"
    )
    _write(target / "day56-execution-log.md", "# Day 56 execution log\n")
    _write(
        target / "day56-delivery-board.md",
        "\n".join(["# Day 56 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day56-validation-commands.md",
        "# Day 56 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day56-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 56 stabilization closeout checks")
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
        _write(root / _PAGE_PATH, _DAY56_DEFAULT_PAGE)

    payload = build_day56_stabilization_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day56-stabilization-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
