from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day53-docs-loop-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY52_SUMMARY_PATH = (
    "docs/artifacts/day52-narrative-closeout-pack/day52-narrative-closeout-summary.json"
)
_DAY52_BOARD_PATH = "docs/artifacts/day52-narrative-closeout-pack/day52-delivery-board.md"
_SECTION_HEADER = "# Day 53 \u2014 Docs loop optimization closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 53 matters",
    "## Required inputs (Day 52)",
    "## Day 53 command lane",
    "## Docs loop optimization contract",
    "## Docs loop quality checklist",
    "## Day 53 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day53-docs-loop-closeout --format json --strict",
    "python -m sdetkit day53-docs-loop-closeout --emit-pack-dir docs/artifacts/day53-docs-loop-closeout-pack --format json --strict",
    "python -m sdetkit day53-docs-loop-closeout --execute --evidence-dir docs/artifacts/day53-docs-loop-closeout-pack/evidence --format json --strict",
    "python scripts/check_day53_docs_loop_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day53-docs-loop-closeout --format json --strict",
    "python -m sdetkit day53-docs-loop-closeout --emit-pack-dir docs/artifacts/day53-docs-loop-closeout-pack --format json --strict",
    "python scripts/check_day53_docs_loop_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 53 docs-loop execution and KPI follow-up.",
    "The Day 53 docs-loop lane references Day 52 narrative winners and misses with deterministic cross-link remediation loops.",
    "Every Day 53 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.",
    "Day 53 closeout records docs-loop learnings and Day 54 re-engagement priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes wins/misses digest, proof snippet draft, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes docs-loop brief, cross-link map, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 53 docs-loop brief committed",
    "- [ ] Day 53 docs-loop plan reviewed with owner + backup",
    "- [ ] Day 53 cross-link map exported",
    "- [ ] Day 53 KPI scorecard snapshot exported",
    "- [ ] Day 54 re-engagement priorities drafted from Day 53 learnings",
]

_DAY53_DEFAULT_PAGE = """# Day 53 \u2014 Docs loop optimization closeout lane

Day 53 closes with a major docs loop optimization upgrade that converts Day 52 narrative evidence into deterministic cross-link execution across demos, playbooks, and CLI docs.

## Why Day 53 matters

- Converts Day 52 narrative proof into a durable docs-loop optimization discipline.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from Day 53 docs-loop upgrades into Day 54 re-engagement execution.

## Required inputs (Day 52)

- `docs/artifacts/day52-narrative-closeout-pack/day52-narrative-closeout-summary.json`
- `docs/artifacts/day52-narrative-closeout-pack/day52-delivery-board.md`

## Day 53 command lane

```bash
python -m sdetkit day53-docs-loop-closeout --format json --strict
python -m sdetkit day53-docs-loop-closeout --emit-pack-dir docs/artifacts/day53-docs-loop-closeout-pack --format json --strict
python -m sdetkit day53-docs-loop-closeout --execute --evidence-dir docs/artifacts/day53-docs-loop-closeout-pack/evidence --format json --strict
python scripts/check_day53_docs_loop_closeout_contract.py
```

## Docs loop optimization contract

- Single owner + backup reviewer are assigned for Day 53 docs-loop execution and KPI follow-up.
- The Day 53 docs-loop lane references Day 52 narrative winners and misses with deterministic cross-link remediation loops.
- Every Day 53 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Day 53 closeout records docs-loop learnings and Day 54 re-engagement priorities.

## Docs loop quality checklist

- [ ] Includes wins/misses digest, proof snippet draft, and rollback strategy
- [ ] Every section has owner, review window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes docs-loop brief, cross-link map, KPI scorecard, and execution log

## Day 53 delivery board

- [ ] Day 53 docs-loop brief committed
- [ ] Day 53 docs-loop plan reviewed with owner + backup
- [ ] Day 53 cross-link map exported
- [ ] Day 53 KPI scorecard snapshot exported
- [ ] Day 54 re-engagement priorities drafted from Day 53 learnings

## Scoring model

Day 53 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 52 continuity and strict baseline carryover: 35 points.
- Docs-loop contract lock + delivery board readiness: 15 points.
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


def _load_day52(path: Path) -> tuple[float, bool, int]:
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


def _contains_all_lines(text: str, required_lines: list[str]) -> list[str]:
    return [line for line in required_lines if line not in text]


def _board_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- [")]
    return len(lines), ("Day 52" in text), ("Day 53" in text)


def build_day53_docs_loop_closeout_summary(root: Path) -> dict[str, Any]:
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

    day52_summary = root / _DAY52_SUMMARY_PATH
    day52_board = root / _DAY52_BOARD_PATH
    day52_score, day52_strict, day52_check_count = _load_day52(day52_summary)
    board_count, board_has_day52, board_has_day53 = _board_stats(day52_board)

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
            "check_id": "readme_day53_link",
            "weight": 8,
            "passed": "docs/integrations-day53-docs-loop-closeout.md" in readme_text,
            "evidence": "docs/integrations-day53-docs-loop-closeout.md",
        },
        {
            "check_id": "readme_day53_command",
            "weight": 4,
            "passed": "day53-docs-loop-closeout" in readme_text,
            "evidence": "day53-docs-loop-closeout",
        },
        {
            "check_id": "docs_index_day53_links",
            "weight": 8,
            "passed": (
                "day-53-big-upgrade-report.md" in docs_index_text
                and "integrations-day53-docs-loop-closeout.md" in docs_index_text
            ),
            "evidence": "day-53-big-upgrade-report.md + integrations-day53-docs-loop-closeout.md",
        },
        {
            "check_id": "top10_day53_alignment",
            "weight": 5,
            "passed": ("Day 52" in top10_text and "Day 53" in top10_text),
            "evidence": "Day 52 + Day 53 strategy chain",
        },
        {
            "check_id": "day52_summary_present",
            "weight": 10,
            "passed": day52_summary.exists(),
            "evidence": str(day52_summary),
        },
        {
            "check_id": "day52_delivery_board_present",
            "weight": 8,
            "passed": day52_board.exists(),
            "evidence": str(day52_board),
        },
        {
            "check_id": "day52_quality_floor",
            "weight": 10,
            "passed": day52_strict and day52_score >= 95,
            "evidence": {
                "day52_score": day52_score,
                "strict_pass": day52_strict,
                "day52_checks": day52_check_count,
            },
        },
        {
            "check_id": "day52_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day52 and board_has_day53,
            "evidence": {
                "board_items": board_count,
                "contains_day52": board_has_day52,
                "contains_day53": board_has_day53,
            },
        },
        {
            "check_id": "docs_loop_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "docs_loop_quality_checklist_locked",
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
    if not day52_summary.exists() or not day52_board.exists():
        critical_failures.append("day52_handoff_inputs")
    if not day52_strict:
        critical_failures.append("day52_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day52_strict:
        wins.append(f"Day 52 continuity is strict-pass with activation score={day52_score}.")
    else:
        misses.append("Day 52 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 52 narrative closeout command and restore strict pass baseline before Day 53 lock."
        )

    if board_count >= 5 and board_has_day52 and board_has_day53:
        wins.append(
            f"Day 52 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 52 delivery board integrity is incomplete (needs >=5 items and Day 52/53 anchors)."
        )
        handoff_actions.append(
            "Repair Day 52 delivery board entries to include Day 52 and Day 53 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Docs-loop contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Docs-loop contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 53 docs-loop contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 53 docs-loop closeout lane is fully complete and ready for Day 54 execution lane."
        )

    return {
        "name": "day53-docs-loop-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day52_summary": str(day52_summary.relative_to(root))
            if day52_summary.exists()
            else str(day52_summary),
            "day52_delivery_board": str(day52_board.relative_to(root))
            if day52_board.exists()
            else str(day52_board),
        },
        "checks": checks,
        "rollup": {
            "day52_activation_score": day52_score,
            "day52_checks": day52_check_count,
            "day52_delivery_board_items": board_count,
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
        "Day 53 docs-loop closeout summary",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- Day 52 activation score: `{payload['rollup']['day52_activation_score']}`",
        f"- Day 52 checks evaluated: `{payload['rollup']['day52_checks']}`",
        f"- Day 52 delivery board checklist items: `{payload['rollup']['day52_delivery_board_items']}`",
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
    _write(target / "day53-docs-loop-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day53-docs-loop-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "day53-docs-loop-brief.md",
        "# Day 53 Docs-loop Brief\n\n- Objective: close Day 53 with measurable docs-loop optimization gains and proof-backed cross-link quality.\n",
    )
    _write(
        target / "day53-cross-link-map.csv",
        "stream,owner,backup,review_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "docs-loop-floor,qa-lead,docs-owner,2026-03-20T10:00:00Z,docs/integrations-day53-docs-loop-closeout.md,python -m sdetkit day53-docs-loop-closeout --format json --strict,failed-checks:0,link-drift\n",
    )
    _write(
        target / "day53-docs-loop-kpi-scorecard.json",
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
        target / "day53-execution-log.md",
        "# Day 53 Execution Log\n\n- [ ] 2026-03-20: Record misses, wins, and Day 54 re-engagement priorities.\n",
    )
    _write(
        target / "day53-delivery-board.md",
        "# Day 53 Delivery Board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day53-validation-commands.md",
        "# Day 53 Validation Commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        evidence_path / "day53-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 53 docs-loop closeout checks")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--ensure-doc", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.ensure_doc:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DAY53_DEFAULT_PAGE)

    payload = build_day53_docs_loop_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day53-docs-loop-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
