from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-case-snippet-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY50_SUMMARY_PATH = "docs/artifacts/execution-prioritization-closeout-pack/execution-prioritization-closeout-summary.json"
_DAY50_BOARD_PATH = "docs/artifacts/execution-prioritization-closeout-pack/execution-prioritization-delivery-board.md"
_DAY50_LEGACY_SUMMARY_PATH = "docs/artifacts/execution-prioritization-closeout-pack-50/execution-prioritization-closeout-summary-50.json"
_DAY50_LEGACY_BOARD_PATH = (
    "docs/artifacts/execution-prioritization-closeout-pack-50/delivery-board-50.md"
)
_SECTION_HEADER = "# Cycle 51 \u2014 Case snippet closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Cycle 51 matters",
    "## Required inputs (Day 50)",
    "## Cycle 51 command lane",
    "## Case snippet closeout contract",
    "## Case snippet quality checklist",
    "## Cycle 51 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit case-snippet-closeout --format json --strict",
    "python -m sdetkit case-snippet-closeout --emit-pack-dir docs/artifacts/case-snippet-closeout-pack --format json --strict",
    "python -m sdetkit case-snippet-closeout --execute --evidence-dir docs/artifacts/case-snippet-closeout-pack/evidence --format json --strict",
    "python scripts/check_case_snippet_closeout_contract_51.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit case-snippet-closeout --format json --strict",
    "python -m sdetkit case-snippet-closeout --emit-pack-dir docs/artifacts/case-snippet-closeout-pack --format json --strict",
    "python scripts/check_case_snippet_closeout_contract_51.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Cycle 51 case snippet execution and KPI follow-up.",
    "The Cycle 51 case snippet lane references Day 50 execution-prioritization winners and misses with deterministic release-storytelling loops.",
    "Every Cycle 51 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.",
    "Cycle 51 closeout records case-snippet learnings and Cycle 52 narrative priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes wins/misses digest, proof snippet draft, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes case brief, proof map, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Cycle 51 case snippet brief committed",
    "- [ ] Cycle 51 snippet reviewed with owner + backup",
    "- [ ] Cycle 51 proof map exported",
    "- [ ] Cycle 51 KPI scorecard snapshot exported",
    "- [ ] Cycle 52 narrative priorities drafted from Cycle 51 learnings",
]

_DEFAULT_PAGE_TEMPLATE = """# Cycle 51 \u2014 Case snippet closeout lane

Cycle 51 closes with a major case-snippet upgrade that converts Day 50 execution-prioritization evidence into a deterministic release-storytelling lane.

## Why Cycle 51 matters

- Converts Day 50 execution-prioritization proof into release-storytelling discipline.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from Cycle 51 case snippets into Cycle 52 narrative execution.

## Required inputs (Day 50)

- `docs/artifacts/execution-prioritization-closeout-pack/execution-prioritization-closeout-summary.json`
- `docs/artifacts/execution-prioritization-closeout-pack/execution-prioritization-delivery-board.md`

## Cycle 51 command lane

```bash
python -m sdetkit case-snippet-closeout --format json --strict
python -m sdetkit case-snippet-closeout --emit-pack-dir docs/artifacts/case-snippet-closeout-pack --format json --strict
python -m sdetkit case-snippet-closeout --execute --evidence-dir docs/artifacts/case-snippet-closeout-pack/evidence --format json --strict
python scripts/check_case_snippet_closeout_contract_51.py
```

## Case snippet closeout contract

- Single owner + backup reviewer are assigned for Cycle 51 case snippet execution and KPI follow-up.
- The Cycle 51 case snippet lane references Day 50 execution-prioritization winners and misses with deterministic release-storytelling loops.
- Every Cycle 51 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Cycle 51 closeout records case-snippet learnings and Cycle 52 narrative priorities.

## Case snippet quality checklist

- [ ] Includes wins/misses digest, proof snippet draft, and rollback strategy
- [ ] Every section has owner, review window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes case brief, proof map, KPI scorecard, and execution log

## Cycle 51 delivery board

- [ ] Cycle 51 case snippet brief committed
- [ ] Cycle 51 snippet reviewed with owner + backup
- [ ] Cycle 51 proof map exported
- [ ] Cycle 51 KPI scorecard snapshot exported
- [ ] Cycle 52 narrative priorities drafted from Cycle 51 learnings

## Scoring model

Cycle 51 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 50 continuity and strict baseline carryover: 35 points.
- Case snippet contract lock + delivery board readiness: 15 points.
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


def _load_day50(path: Path) -> tuple[float, bool, int]:
    data_obj = _load_json(path)
    if not isinstance(data_obj, dict):
        return 0.0, False, 0
    summary_obj = data_obj.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    checks_obj = data_obj.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    score = float(summary.get("activation_score", 0.0))
    strict = bool(summary.get("strict_pass", False))
    check_count = len(checks)
    return score, strict, check_count


def _resolve_day50_inputs(root: Path) -> tuple[Path, Path]:
    summary = root / _DAY50_SUMMARY_PATH
    board = root / _DAY50_BOARD_PATH
    if summary.exists() and board.exists():
        return summary, board
    legacy_summary = root / _DAY50_LEGACY_SUMMARY_PATH
    legacy_board = root / _DAY50_LEGACY_BOARD_PATH
    if legacy_summary.exists() and legacy_board.exists():
        return legacy_summary, legacy_board
    return summary, board


def _contains_all_lines(text: str, required_lines: list[str]) -> list[str]:
    return [line for line in required_lines if line not in text]


def _board_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- [")]
    return len(lines), ("Day 50" in text), ("Cycle 51" in text)


def build_case_snippet_closeout_summary(root: Path) -> dict[str, Any]:
    readme_path = "README.md"
    docs_index_path = "docs/index.md"
    docs_page_path = _PAGE_PATH
    top10_path = _TOP10_PATH

    readme_text = _read(root / readme_path)
    docs_index_text = _read(root / docs_index_path)
    page_path = root / docs_page_path
    page_text = _read(page_path)
    top10_text = _read(root / top10_path)

    missing_sections = [
        item for item in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if item not in page_text
    ]
    missing_commands = _contains_all_lines(page_text, _REQUIRED_COMMANDS)
    missing_contract_lines = _contains_all_lines(
        page_text, [f"- {line}" for line in _REQUIRED_CONTRACT_LINES]
    )
    missing_quality_lines = _contains_all_lines(page_text, _REQUIRED_QUALITY_LINES)
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    day50_summary, day50_board = _resolve_day50_inputs(root)
    day50_score, day50_strict, day50_check_count = _load_day50(day50_summary)
    board_count, board_has_day50, board_has_cycle51 = _board_stats(day50_board)

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
            "check_id": "readme_cycle51_link",
            "weight": 8,
            "passed": "docs/integrations-case-snippet-closeout.md" in readme_text,
            "evidence": "docs/integrations-case-snippet-closeout.md",
        },
        {
            "check_id": "readme_cycle51_command",
            "weight": 4,
            "passed": "case-snippet-closeout" in readme_text,
            "evidence": "case-snippet-closeout",
        },
        {
            "check_id": "docs_index_cycle51_links",
            "weight": 8,
            "passed": (
                "impact-51-big-upgrade-report.md" in docs_index_text
                and "integrations-case-snippet-closeout.md" in docs_index_text
            ),
            "evidence": "impact-51-big-upgrade-report.md + integrations-case-snippet-closeout.md",
        },
        {
            "check_id": "top10_cycle51_alignment",
            "weight": 5,
            "passed": ("Cycle 51" in top10_text and "Cycle 52" in top10_text),
            "evidence": "Cycle 51 + Cycle 52 strategy chain",
        },
        {
            "check_id": "day50_summary_present",
            "weight": 10,
            "passed": day50_summary.exists(),
            "evidence": str(day50_summary),
        },
        {
            "check_id": "day50_delivery_board_present",
            "weight": 8,
            "passed": day50_board.exists(),
            "evidence": str(day50_board),
        },
        {
            "check_id": "day50_quality_floor",
            "weight": 10,
            "passed": day50_strict and day50_score >= 95,
            "evidence": {
                "day50_score": day50_score,
                "strict_pass": day50_strict,
                "day50_checks": day50_check_count,
            },
        },
        {
            "check_id": "day50_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day50 and board_has_cycle51,
            "evidence": {
                "board_items": board_count,
                "contains_day50": board_has_day50,
                "contains_cycle51": board_has_cycle51,
            },
        },
        {
            "check_id": "case_snippet_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "case_snippet_quality_checklist_locked",
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
    score = int(round(sum(c["weight"] for c in checks if bool(c["passed"]))))
    critical_failures: list[str] = []
    if not day50_summary.exists() or not day50_board.exists():
        critical_failures.append("day50_handoff_inputs")
    if not day50_strict:
        critical_failures.append("day50_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day50_strict:
        wins.append(f"Day 50 continuity is strict-pass with activation score={day50_score}.")
    else:
        misses.append("Day 50 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 50 execution prioritization closeout command and restore strict pass baseline before Cycle 51 lock."
        )

    if board_count >= 5 and board_has_day50 and board_has_cycle51:
        wins.append(
            f"Day 50 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 50 delivery board integrity is incomplete (needs >=5 items and Day 50/51 anchors)."
        )
        handoff_actions.append(
            "Repair Day 50 delivery board entries to include Day 50 and Cycle 51 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Case snippet contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Case snippet contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Cycle 51 case snippet contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Cycle 51 case snippet closeout lane is fully complete and ready for Cycle 52 execution lane."
        )

    return {
        "name": "case-snippet-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day50_summary": str(day50_summary.relative_to(root))
            if day50_summary.exists()
            else str(day50_summary),
            "day50_delivery_board": str(day50_board.relative_to(root))
            if day50_board.exists()
            else str(day50_board),
        },
        "checks": checks,
        "rollup": {
            "day50_activation_score": day50_score,
            "day50_checks": day50_check_count,
            "day50_delivery_board_items": board_count,
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
        "Case Snippet Closeout summary (legacy: Cycle 51)",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- Day 50 activation score: `{payload['rollup']['day50_activation_score']}`",
        f"- Day 50 checks evaluated: `{payload['rollup']['day50_checks']}`",
        f"- Day 50 delivery board checklist items: `{payload['rollup']['day50_delivery_board_items']}`",
    ]
    if payload["wins"]:
        lines.append("- Wins:")
        lines.extend([f"  - {w}" for w in payload["wins"]])
    if payload["misses"]:
        lines.append("- Misses:")
        lines.extend([f"  - {m}" for m in payload["misses"]])
    return "\n".join(lines)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _emit_pack(root: Path, payload: dict[str, Any], pack_dir: Path) -> None:
    target = root / pack_dir
    target.mkdir(parents=True, exist_ok=True)
    _write(target / "case-snippet-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "case-snippet-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "case-snippet-brief.md",
        "# Cycle 51 Case Snippet Brief\n\n- Objective: close Cycle 51 with measurable release-storytelling discipline and proof-backed narrative gains.\n",
    )
    _write(
        target / "proof-map.csv",
        "stream,owner,backup,review_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "case-snippet-floor,qa-lead,docs-owner,2026-03-19T10:00:00Z,docs/integrations-case-snippet-closeout.md,python -m sdetkit case-snippet-closeout --format json --strict,failed-checks:0,narrative-drift\n",
    )
    _write(
        target / "case-snippet-kpi-scorecard.json",
        json.dumps(
            {
                "kpis": [
                    {
                        "id": "strict_pass",
                        "baseline": 1,
                        "current": int(payload["summary"]["strict_pass"]),
                        "delta": int(payload["summary"]["strict_pass"]) - 1,
                        "confidence": "high",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "execution-log.md",
        "# Cycle 51 Execution Log\n\n- [ ] 2026-03-19: Record misses, wins, and Cycle 52 narrative priorities.\n",
    )
    _write(
        target / "delivery-board.md",
        "# Cycle 51 Delivery Board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "validation-commands.md",
        "# Cycle 51 Validation Commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    evidence_path = root / evidence_dir
    evidence_path.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = []
    for index, command in enumerate(_EXECUTION_COMMANDS, start=1):
        argv = shlex.split(command)
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        proc = subprocess.run(argv, cwd=root, text=True, capture_output=True, check=False)
        event = {
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        events.append(event)
        _write(evidence_path / f"command-{index:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        evidence_path / "execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Case Snippet Closeout checks (legacy alias: case-snippet-closeout)"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--ensure-doc", action="store_true")
    return parser


def build_cycle51_case_snippet_closeout_summary(root: Path) -> dict[str, Any]:
    """Compatibility alias for legacy cycle-based builder name."""
    return build_case_snippet_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.ensure_doc:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DEFAULT_PAGE_TEMPLATE)

    payload = build_case_snippet_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/case-snippet-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
