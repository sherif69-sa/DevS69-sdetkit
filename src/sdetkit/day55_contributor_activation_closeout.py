from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day55-contributor-activation-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY53_SUMMARY_PATH = (
    "docs/artifacts/day53-docs-loop-closeout-pack/day53-docs-loop-closeout-summary.json"
)
_DAY53_BOARD_PATH = "docs/artifacts/day53-docs-loop-closeout-pack/day53-delivery-board.md"
_SECTION_HEADER = "# Day 55 \u2014 Contributor activation closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 55 matters",
    "## Required inputs (Day 53)",
    "## Day 55 command lane",
    "## Contributor activation contract",
    "## Contributor activation quality checklist",
    "## Day 55 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day55-contributor-activation-closeout --format json --strict",
    "python -m sdetkit day55-contributor-activation-closeout --emit-pack-dir docs/artifacts/day55-contributor-activation-closeout-pack --format json --strict",
    "python -m sdetkit day55-contributor-activation-closeout --execute --evidence-dir docs/artifacts/day55-contributor-activation-closeout-pack/evidence --format json --strict",
    "python scripts/check_day55_contributor_activation_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day55-contributor-activation-closeout --format json --strict",
    "python -m sdetkit day55-contributor-activation-closeout --emit-pack-dir docs/artifacts/day55-contributor-activation-closeout-pack --format json --strict",
    "python scripts/check_day55_contributor_activation_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 55 contributor-activation execution and KPI follow-up.",
    "The Day 55 lane references Day 53 docs-loop wins and misses with deterministic contributor follow-up loops.",
    "Every Day 55 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.",
    "Day 55 closeout records contributor-activation learnings and Day 56 prioritization inputs.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes wins/misses digest, activation experiments, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes contributor brief, contributor ladder, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 55 contributor brief committed",
    "- [ ] Day 55 activation plan reviewed with owner + backup",
    "- [ ] Day 55 contributor ladder exported",
    "- [ ] Day 55 KPI scorecard snapshot exported",
    "- [ ] Day 56 priorities drafted from Day 55 learnings",
]

_DAY55_DEFAULT_PAGE = """# Day 55 \u2014 Contributor activation closeout lane

Day 55 closes with a major contributor activation upgrade that turns Day 53 docs-loop evidence into a deterministic contributor follow-through lane.

## Why Day 55 matters

- Converts Day 53 docs-loop wins into repeatable contributor activation motions.
- Protects quality with ownership, command proof, and KPI guardrails.
- Produces a deterministic handoff from Day 55 closeout into Day 56 planning.

## Required inputs (Day 53)

- `docs/artifacts/day53-docs-loop-closeout-pack/day53-docs-loop-closeout-summary.json`
- `docs/artifacts/day53-docs-loop-closeout-pack/day53-delivery-board.md`

## Day 55 command lane

```bash
python -m sdetkit day55-contributor-activation-closeout --format json --strict
python -m sdetkit day55-contributor-activation-closeout --emit-pack-dir docs/artifacts/day55-contributor-activation-closeout-pack --format json --strict
python -m sdetkit day55-contributor-activation-closeout --execute --evidence-dir docs/artifacts/day55-contributor-activation-closeout-pack/evidence --format json --strict
python scripts/check_day55_contributor_activation_closeout_contract.py
```

## Contributor activation contract

- Single owner + backup reviewer are assigned for Day 55 contributor-activation execution and KPI follow-up.
- The Day 55 lane references Day 53 docs-loop wins and misses with deterministic contributor follow-up loops.
- Every Day 55 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Day 55 closeout records contributor-activation learnings and Day 56 prioritization inputs.

## Contributor activation quality checklist

- [ ] Includes wins/misses digest, activation experiments, and rollback strategy
- [ ] Every section has owner, review window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes contributor brief, contributor ladder, KPI scorecard, and execution log

## Day 55 delivery board

- [ ] Day 55 contributor brief committed
- [ ] Day 55 activation plan reviewed with owner + backup
- [ ] Day 55 contributor ladder exported
- [ ] Day 55 KPI scorecard snapshot exported
- [ ] Day 56 priorities drafted from Day 55 learnings

## Scoring model

Day 55 weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 53 continuity and strict baseline carryover: 35 points.
- Activation contract lock + delivery board readiness: 15 points.
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


def _load_day53(path: Path) -> tuple[float, bool, int]:
    data = _load_json(path)
    if data is None:
        return 0.0, False, 0
    summary = data.get("summary")
    checks = data.get("checks")
    if not isinstance(summary, dict) or not isinstance(checks, list):
        return 0.0, False, 0
    score = float(summary.get("activation_score", 0.0))
    strict = bool(summary.get("strict_pass", False))
    return score, strict, len(checks)


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def _board_stats(path: Path) -> tuple[int, bool]:
    text = _read(path)
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- [")]
    return len(lines), ("Day 53" in text)


def build_day55_contributor_activation_closeout_summary(root: Path) -> dict[str, Any]:
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

    day53_summary = root / _DAY53_SUMMARY_PATH
    day53_board = root / _DAY53_BOARD_PATH
    day53_score, day53_strict, day53_check_count = _load_day53(day53_summary)
    board_count, board_has_day53 = _board_stats(day53_board)

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
            "check_id": "readme_day55_link",
            "weight": 8,
            "passed": _PAGE_PATH in readme_text,
            "evidence": _PAGE_PATH,
        },
        {
            "check_id": "readme_day55_command",
            "weight": 4,
            "passed": "day55-contributor-activation-closeout" in readme_text,
            "evidence": "day55-contributor-activation-closeout",
        },
        {
            "check_id": "docs_index_day55_links",
            "weight": 8,
            "passed": (
                "day-55-big-upgrade-report.md" in docs_index_text
                and "integrations-day55-contributor-activation-closeout.md" in docs_index_text
            ),
            "evidence": "day-55-big-upgrade-report.md + integrations-day55-contributor-activation-closeout.md",
        },
        {
            "check_id": "top10_day55_alignment",
            "weight": 5,
            "passed": ("Day 55" in top10_text and "Day 56" in top10_text),
            "evidence": "Day 55 + Day 56 strategy chain",
        },
        {
            "check_id": "day53_summary_present",
            "weight": 10,
            "passed": day53_summary.exists(),
            "evidence": str(day53_summary),
        },
        {
            "check_id": "day53_delivery_board_present",
            "weight": 8,
            "passed": day53_board.exists(),
            "evidence": str(day53_board),
        },
        {
            "check_id": "day53_quality_floor",
            "weight": 10,
            "passed": day53_strict and day53_score >= 95,
            "evidence": {
                "day53_score": day53_score,
                "strict_pass": day53_strict,
                "day53_checks": day53_check_count,
            },
        },
        {
            "check_id": "day53_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day53,
            "evidence": {"board_items": board_count, "contains_day53": board_has_day53},
        },
        {
            "check_id": "activation_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "activation_quality_checklist_locked",
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
    if not day53_summary.exists() or not day53_board.exists():
        critical_failures.append("day53_handoff_inputs")
    if not day53_strict:
        critical_failures.append("day53_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day53_strict:
        wins.append(f"Day 53 continuity is strict-pass with activation score={day53_score}.")
    else:
        misses.append("Day 53 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 53 docs-loop closeout command and restore strict baseline before Day 55 lock."
        )

    if board_count >= 5 and board_has_day53:
        wins.append(
            f"Day 53 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 53 delivery board integrity is incomplete (needs >=5 items and Day 53 anchors)."
        )
        handoff_actions.append("Repair Day 53 delivery board entries to include Day 53 anchors.")

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Contributor activation contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Contributor activation contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 55 contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 55 contributor activation closeout lane is fully complete and ready for Day 56 execution lane."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day55-contributor-activation-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day53_summary": str(day53_summary.relative_to(root))
            if day53_summary.exists()
            else str(day53_summary),
            "day53_delivery_board": str(day53_board.relative_to(root))
            if day53_board.exists()
            else str(day53_board),
        },
        "checks": checks,
        "rollup": {
            "day53_activation_score": day53_score,
            "day53_checks": day53_check_count,
            "day53_delivery_board_items": board_count,
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
        "Day 55 contributor activation closeout summary",
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
        target / "day55-contributor-activation-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(
        target / "day55-contributor-activation-closeout-summary.md", _render_text(payload) + "\n"
    )
    _write(
        target / "day55-contributor-activation-brief.md", "# Day 55 contributor activation brief\n"
    )
    _write(target / "day55-contributor-ladder.csv", "stage,owner,kpi\n")
    _write(
        target / "day55-contributor-activation-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(target / "day55-execution-log.md", "# Day 55 execution log\n")
    _write(
        target / "day55-delivery-board.md",
        "\n".join(["# Day 55 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day55-validation-commands.md",
        "# Day 55 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day55-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 55 contributor activation closeout checks")
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
        _write(root / _PAGE_PATH, _DAY55_DEFAULT_PAGE)

    payload = build_day55_contributor_activation_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day55-contributor-activation-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
