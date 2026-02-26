from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day44-scale-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY43_SUMMARY_PATH = (
    "docs/artifacts/day43-acceleration-closeout-pack/day43-acceleration-closeout-summary.json"
)
_DAY43_BOARD_PATH = "docs/artifacts/day43-acceleration-closeout-pack/day43-delivery-board.md"
_SECTION_HEADER = "# Day 44 — Scale closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 44 matters",
    "## Required inputs (Day 43)",
    "## Day 44 command lane",
    "## Scale closeout contract",
    "## Scale quality checklist",
    "## Day 44 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day44-scale-closeout --format json --strict",
    "python -m sdetkit day44-scale-closeout --emit-pack-dir docs/artifacts/day44-scale-closeout-pack --format json --strict",
    "python -m sdetkit day44-scale-closeout --execute --evidence-dir docs/artifacts/day44-scale-closeout-pack/evidence --format json --strict",
    "python scripts/check_day44_scale_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day44-scale-closeout --format json --strict",
    "python -m sdetkit day44-scale-closeout --emit-pack-dir docs/artifacts/day44-scale-closeout-pack --format json --strict",
    "python scripts/check_day44_scale_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 44 scale lane execution and KPI follow-up.",
    "The Day 44 scale lane references Day 43 acceleration winners and misses with deterministic growth loops.",
    "Every Day 44 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.",
    "Day 44 closeout records scale learnings and Day 45 expansion priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes scale summary, growth matrix, and rollback strategy",
    "- [ ] Every section has owner, publish window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes scale plan, growth matrix, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 44 scale plan draft committed",
    "- [ ] Day 44 review notes captured with owner + backup",
    "- [ ] Day 44 growth matrix exported",
    "- [ ] Day 44 KPI scorecard snapshot exported",
    "- [ ] Day 45 expansion priorities drafted from Day 44 learnings",
]

_DAY44_DEFAULT_PAGE = """# Day 44 — Scale closeout lane

Day 44 closes with a major scale upgrade that converts Day 43 acceleration evidence into deterministic improvement loops.

## Why Day 44 matters

- Converts Day 43 acceleration proof into growth-first operating motion.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from scale outcomes into Day 45 expansion priorities.

## Required inputs (Day 43)

- `docs/artifacts/day43-acceleration-closeout-pack/day43-acceleration-closeout-summary.json`
- `docs/artifacts/day43-acceleration-closeout-pack/day43-delivery-board.md`

## Day 44 command lane

```bash
python -m sdetkit day44-scale-closeout --format json --strict
python -m sdetkit day44-scale-closeout --emit-pack-dir docs/artifacts/day44-scale-closeout-pack --format json --strict
python -m sdetkit day44-scale-closeout --execute --evidence-dir docs/artifacts/day44-scale-closeout-pack/evidence --format json --strict
python scripts/check_day44_scale_closeout_contract.py
```

## Scale closeout contract

- Single owner + backup reviewer are assigned for Day 44 scale lane execution and KPI follow-up.
- The Day 44 scale lane references Day 43 acceleration winners and misses with deterministic growth loops.
- Every Day 44 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Day 44 closeout records scale learnings and Day 45 expansion priorities.

## Scale quality checklist

- [ ] Includes scale summary, growth matrix, and rollback strategy
- [ ] Every section has owner, publish window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes scale plan, growth matrix, KPI scorecard, and execution log

## Day 44 delivery board

- [ ] Day 44 scale plan draft committed
- [ ] Day 44 review notes captured with owner + backup
- [ ] Day 44 growth matrix exported
- [ ] Day 44 KPI scorecard snapshot exported
- [ ] Day 45 expansion priorities drafted from Day 44 learnings

## Scoring model

Day 44 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 43 continuity and strict baseline carryover: 35 points.
- Scale contract lock + delivery board readiness: 15 points.
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


def _load_day43(path: Path) -> tuple[float, bool, int]:
    data = _load_json(path)
    if data is None:
        return 0.0, False, 0
    summary = data.get("summary")
    checks = data.get("checks")
    score = summary.get("activation_score") if isinstance(summary, dict) else None
    strict_pass = summary.get("strict_pass") if isinstance(summary, dict) else False
    check_count = len(checks) if isinstance(checks, list) else 0
    resolved_score = float(score) if isinstance(score, (int, float)) else 0.0
    return resolved_score, bool(strict_pass), check_count


def _board_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    items = [line for line in text.splitlines() if line.strip().startswith("- [")]
    return len(items), "Day 43" in text, "Day 44" in text


def _contains_all_lines(text: str, expected: list[str]) -> list[str]:
    return [line for line in expected if line not in text]


def build_day44_scale_closeout_summary(root: Path) -> dict[str, Any]:
    readme_path = "README.md"
    docs_index_path = "docs/index.md"
    docs_page_path = _PAGE_PATH
    top10_path = _TOP10_PATH

    page_path = root / docs_page_path
    page_text = _read(page_path)
    readme_text = _read(root / readme_path)
    docs_index_text = _read(root / docs_index_path)
    top10_text = _read(root / top10_path)

    missing_sections = [s for s in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if s not in page_text]
    missing_commands = [c for c in _REQUIRED_COMMANDS if c not in page_text]
    missing_contract_lines = _contains_all_lines(
        page_text, [f"- {line}" for line in _REQUIRED_CONTRACT_LINES]
    )
    missing_quality_lines = _contains_all_lines(page_text, _REQUIRED_QUALITY_LINES)
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    day43_summary = root / _DAY43_SUMMARY_PATH
    day43_board = root / _DAY43_BOARD_PATH
    day43_score, day43_strict, day43_check_count = _load_day43(day43_summary)
    board_count, board_has_day43, board_has_day44 = _board_stats(day43_board)

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
            "check_id": "readme_day44_link",
            "weight": 8,
            "passed": "docs/integrations-day44-scale-closeout.md" in readme_text,
            "evidence": "docs/integrations-day44-scale-closeout.md",
        },
        {
            "check_id": "readme_day44_command",
            "weight": 4,
            "passed": "day44-scale-closeout" in readme_text,
            "evidence": "day44-scale-closeout",
        },
        {
            "check_id": "docs_index_day44_links",
            "weight": 8,
            "passed": (
                "day-44-big-upgrade-report.md" in docs_index_text
                and "integrations-day44-scale-closeout.md" in docs_index_text
            ),
            "evidence": "day-44-big-upgrade-report.md + integrations-day44-scale-closeout.md",
        },
        {
            "check_id": "top10_day44_alignment",
            "weight": 5,
            "passed": ("Day 44" in top10_text and "Day 45" in top10_text),
            "evidence": "Day 44 + Day 45 strategy chain",
        },
        {
            "check_id": "day43_summary_present",
            "weight": 10,
            "passed": day43_summary.exists(),
            "evidence": str(day43_summary),
        },
        {
            "check_id": "day43_delivery_board_present",
            "weight": 8,
            "passed": day43_board.exists(),
            "evidence": str(day43_board),
        },
        {
            "check_id": "day43_quality_floor",
            "weight": 10,
            "passed": day43_strict and day43_score >= 95,
            "evidence": {
                "day43_score": day43_score,
                "strict_pass": day43_strict,
                "day43_checks": day43_check_count,
            },
        },
        {
            "check_id": "day43_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day43 and board_has_day44,
            "evidence": {
                "board_items": board_count,
                "contains_day43": board_has_day43,
                "contains_day44": board_has_day44,
            },
        },
        {
            "check_id": "scale_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "scale_quality_checklist_locked",
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
    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    critical_failures: list[str] = []
    if not day43_summary.exists() or not day43_board.exists():
        critical_failures.append("day43_handoff_inputs")
    if not day43_strict:
        critical_failures.append("day43_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day43_strict:
        wins.append(f"Day 43 continuity is strict-pass with activation score={day43_score}.")
    else:
        misses.append("Day 43 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 43 acceleration closeout command and restore strict pass baseline before Day 44 lock."
        )

    if board_count >= 5 and board_has_day43 and board_has_day44:
        wins.append(
            f"Day 43 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 43 delivery board integrity is incomplete (needs >=5 items and Day 43/44 anchors)."
        )
        handoff_actions.append(
            "Repair Day 43 delivery board entries to include Day 43 and Day 44 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Scale execution contract + quality checklist is fully locked for execution.")
    else:
        misses.append("Scale contract, quality checklist, or delivery board entries are missing.")
        handoff_actions.append(
            "Complete all Day 44 scale contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 44 scale closeout lane is fully complete and ready for Day 45 expansion lane."
        )

    return {
        "name": "day44-scale-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day43_summary": str(day43_summary.relative_to(root))
            if day43_summary.exists()
            else str(day43_summary),
            "day43_delivery_board": str(day43_board.relative_to(root))
            if day43_board.exists()
            else str(day43_board),
        },
        "checks": checks,
        "rollup": {
            "day43_activation_score": day43_score,
            "day43_checks": day43_check_count,
            "day43_delivery_board_items": board_count,
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
        "Day 44 scale closeout summary",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- Day 43 activation score: `{payload['rollup']['day43_activation_score']}`",
        f"- Day 43 checks evaluated: `{payload['rollup']['day43_checks']}`",
        f"- Day 43 delivery board checklist items: `{payload['rollup']['day43_delivery_board_items']}`",
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
    _write(target / "day44-scale-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day44-scale-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "day44-scale-plan.md",
        "# Day 44 Scale Plan\n\n- Objective: close Day 44 with measurable quality and throughput gains.\n",
    )
    _write(
        target / "day44-growth-matrix.csv",
        "stream,owner,backup,publish_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "quality-floor,qa-lead,platform-owner,2026-03-12T10:00:00Z,docs/integrations-day44-scale-closeout.md,python -m sdetkit day44-scale-closeout --format json --strict,failed-checks:0,baseline-drift\n",
    )
    _write(
        target / "day44-scale-kpi-scorecard.json",
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
        target / "day44-execution-log.md",
        "# Day 44 Execution Log\n\n- [ ] 2026-03-12: Record misses, wins, and Day 45 expansion priorities.\n",
    )
    _write(
        target / "day44-delivery-board.md",
        "# Day 44 Delivery Board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day44-validation-commands.md",
        "# Day 44 Validation Commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    evidence_path = root / evidence_dir
    evidence_path.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = []
    for index, command in enumerate(_EXECUTION_COMMANDS, start=1):
        proc = subprocess.run(
            shlex.split(command), cwd=root, text=True, capture_output=True, check=False
        )
        event = {
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        events.append(event)
        _write(evidence_path / f"command-{index:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        evidence_path / "day44-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 44 scale closeout checks")
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
            _write(page, _DAY44_DEFAULT_PAGE)

    payload = build_day44_scale_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day44-scale-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
