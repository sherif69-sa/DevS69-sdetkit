from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-acceleration-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY42_SUMMARY_PATH = (
    "docs/artifacts/optimization-closeout-pack-42/optimization-closeout-summary-42.json"
)
_DAY42_BOARD_PATH = "docs/artifacts/optimization-closeout-pack-42/delivery-board-42.md"
_DAY42_LEGACY_SUMMARY_PATH = "docs/artifacts/optimization-closeout-foundation-pack/optimization-closeout-foundation-summary.json"
_DAY42_LEGACY_BOARD_PATH = "docs/artifacts/optimization-closeout-foundation-pack/delivery-board.md"
_SECTION_HEADER = "# Day 43 \u2014 Acceleration closeout lane"
_REQUIRED_SECTIONS = [
    "## Why this lane matters",
    "## Required inputs (optimization closeout foundation)",
    "## Command lane",
    "## Acceleration closeout contract",
    "## Acceleration quality checklist",
    "## Delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit acceleration-closeout --format json --strict",
    "python -m sdetkit acceleration-closeout --emit-pack-dir docs/artifacts/acceleration-closeout-pack --format json --strict",
    "python -m sdetkit acceleration-closeout --execute --evidence-dir docs/artifacts/acceleration-closeout-pack/evidence --format json --strict",
    "python scripts/check_acceleration_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit acceleration-closeout --format json --strict",
    "python -m sdetkit acceleration-closeout --emit-pack-dir docs/artifacts/acceleration-closeout-pack --format json --strict",
    "python scripts/check_acceleration_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 43 acceleration lane execution and KPI follow-up.",
    "The Day 43 acceleration lane references Day 42 optimization winners and misses with deterministic growth loops.",
    "Every Day 43 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.",
    "Day 43 closeout records acceleration learnings and Day 44 scale priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes acceleration summary, growth matrix, and rollback strategy",
    "- [ ] Every section has owner, publish window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes acceleration plan, growth matrix, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 43 acceleration plan draft committed",
    "- [ ] Day 43 review notes captured with owner + backup",
    "- [ ] Day 43 growth matrix exported",
    "- [ ] Day 43 KPI scorecard snapshot exported",
    "- [ ] Day 44 scale priorities drafted from Day 43 learnings",
]

_DEFAULT_PAGE_TEMPLATE = """# Day 43 \u2014 Acceleration closeout lane

This lane closes with a major acceleration upgrade that converts optimization evidence into deterministic improvement loops.

## Why this lane matters

- Converts Day 42 optimization proof into growth-first operating motion.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from acceleration outcomes into Day 44 scale priorities.

## Required inputs (optimization closeout foundation)

- `docs/artifacts/optimization-closeout-pack-42/optimization-closeout-summary-42.json`
- `docs/artifacts/optimization-closeout-pack-42/delivery-board-42.md`

## Command lane

```bash
python -m sdetkit acceleration-closeout --format json --strict
python -m sdetkit acceleration-closeout --emit-pack-dir docs/artifacts/acceleration-closeout-pack --format json --strict
python -m sdetkit acceleration-closeout --execute --evidence-dir docs/artifacts/acceleration-closeout-pack/evidence --format json --strict
python scripts/check_acceleration_closeout_contract.py
```

## Acceleration closeout contract

- Single owner + backup reviewer are assigned for Day 43 acceleration lane execution and KPI follow-up.
- The Day 43 acceleration lane references Day 42 optimization winners and misses with deterministic growth loops.
- Every Day 43 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Day 43 closeout records acceleration learnings and Day 44 scale priorities.

## Acceleration quality checklist

- [ ] Includes acceleration summary, growth matrix, and rollback strategy
- [ ] Every section has owner, publish window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes acceleration plan, growth matrix, KPI scorecard, and execution log

## Delivery board

- [ ] Day 43 acceleration plan draft committed
- [ ] Day 43 review notes captured with owner + backup
- [ ] Day 43 growth matrix exported
- [ ] Day 43 KPI scorecard snapshot exported
- [ ] Day 44 scale priorities drafted from Day 43 learnings

## Scoring model

Day 43 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 42 continuity and strict baseline carryover: 35 points.
- Acceleration contract lock + delivery board readiness: 15 points.
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


def _load_optimization_closeout(path: Path) -> tuple[float, bool, int]:
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
    return len(items), "Day 42" in text, "Day 43" in text


def _contains_all_lines(text: str, expected: list[str]) -> list[str]:
    return [line for line in expected if line not in text]


def _resolve_existing_path(root: Path, primary: str, legacy: str) -> Path:
    primary_path = root / primary
    if primary_path.exists():
        return primary_path
    return root / legacy


def build_acceleration_closeout_summary(root: Path) -> dict[str, Any]:
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

    optimization_closeout_summary = _resolve_existing_path(root, _DAY42_SUMMARY_PATH, _DAY42_LEGACY_SUMMARY_PATH)
    optimization_closeout_board = _resolve_existing_path(root, _DAY42_BOARD_PATH, _DAY42_LEGACY_BOARD_PATH)
    optimization_closeout_score, optimization_closeout_strict, optimization_closeout_check_count = _load_optimization_closeout(optimization_closeout_summary)
    board_count, board_has_optimization_closeout, board_has_acceleration_closeout = _board_stats(optimization_closeout_board)

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
            "check_id": "readme_acceleration_closeout_link",
            "weight": 8,
            "passed": "docs/integrations-acceleration-closeout.md" in readme_text,
            "evidence": "docs/integrations-acceleration-closeout.md",
        },
        {
            "check_id": "readme_acceleration_closeout_command",
            "weight": 4,
            "passed": "acceleration-closeout" in readme_text,
            "evidence": "acceleration-closeout",
        },
        {
            "check_id": "docs_index_acceleration_closeout_links",
            "weight": 8,
            "passed": (
                "impact-43-big-upgrade-report.md" in docs_index_text
                and "integrations-acceleration-closeout.md" in docs_index_text
            ),
            "evidence": "impact-43-big-upgrade-report.md + integrations-acceleration-closeout.md",
        },
        {
            "check_id": "top10_acceleration_closeout_alignment",
            "weight": 5,
            "passed": ("Day 43" in top10_text and "Day 44" in top10_text),
            "evidence": "Day 43 + Day 44 strategy chain",
        },
        {
            "check_id": "optimization_closeout_summary_present",
            "weight": 10,
            "passed": optimization_closeout_summary.exists(),
            "evidence": str(optimization_closeout_summary),
        },
        {
            "check_id": "optimization_closeout_delivery_board_present",
            "weight": 8,
            "passed": optimization_closeout_board.exists(),
            "evidence": str(optimization_closeout_board),
        },
        {
            "check_id": "optimization_closeout_quality_floor",
            "weight": 10,
            "passed": optimization_closeout_strict and optimization_closeout_score >= 95,
            "evidence": {
                "optimization_closeout_score": optimization_closeout_score,
                "strict_pass": optimization_closeout_strict,
                "optimization_closeout_checks": optimization_closeout_check_count,
            },
        },
        {
            "check_id": "optimization_closeout_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_optimization_closeout and board_has_acceleration_closeout,
            "evidence": {
                "board_items": board_count,
                "contains_optimization_closeout": board_has_optimization_closeout,
                "contains_acceleration_closeout": board_has_acceleration_closeout,
            },
        },
        {
            "check_id": "acceleration_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "acceleration_quality_checklist_locked",
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
    if not optimization_closeout_summary.exists() or not optimization_closeout_board.exists():
        critical_failures.append("optimization_closeout_handoff_inputs")
    if not optimization_closeout_strict:
        critical_failures.append("optimization_closeout_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if optimization_closeout_strict:
        wins.append(f"Day 42 continuity is strict-pass with activation score={optimization_closeout_score}.")
    else:
        misses.append("Day 42 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 42 optimization closeout command and restore strict pass baseline before Day 43 lock."
        )

    if board_count >= 5 and board_has_optimization_closeout and board_has_acceleration_closeout:
        wins.append(
            f"Day 42 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 42 delivery board integrity is incomplete (needs >=5 items and Day 42/43 anchors)."
        )
        handoff_actions.append(
            "Repair Day 42 delivery board entries to include Day 42 and Day 43 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Acceleration execution contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Acceleration contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 43 acceleration contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 43 acceleration closeout lane is fully complete and ready for Day 44 scale lane."
        )

    return {
        "name": "acceleration-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "optimization_closeout_summary": str(optimization_closeout_summary.relative_to(root))
            if optimization_closeout_summary.exists()
            else str(optimization_closeout_summary),
            "optimization_closeout_delivery_board": str(optimization_closeout_board.relative_to(root))
            if optimization_closeout_board.exists()
            else str(optimization_closeout_board),
        },
        "checks": checks,
        "rollup": {
            "optimization_closeout_activation_score": optimization_closeout_score,
            "optimization_closeout_checks": optimization_closeout_check_count,
            "optimization_closeout_delivery_board_items": board_count,
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
        "Acceleration closeout summary",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- Day 42 activation score: `{payload['rollup']['optimization_closeout_activation_score']}`",
        f"- Day 42 checks evaluated: `{payload['rollup']['optimization_closeout_checks']}`",
        f"- Day 42 delivery board checklist items: `{payload['rollup']['optimization_closeout_delivery_board_items']}`",
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
    _write(target / "acceleration-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "acceleration-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "acceleration-plan.md",
        "# Acceleration plan\n\n- Objective: close Day 43 with measurable quality and throughput gains.\n",
    )
    _write(
        target / "growth-matrix.csv",
        "stream,owner,backup,publish_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "quality-floor,qa-lead,platform-owner,2026-03-12T10:00:00Z,docs/integrations-acceleration-closeout.md,python -m sdetkit acceleration-closeout --format json --strict,failed-checks:0,baseline-drift\n",
    )
    _write(
        target / "acceleration-kpi-scorecard.json",
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
        "# Acceleration execution log\n\n- [ ] 2026-03-12: Record misses, wins, and Day 44 scale priorities.\n",
    )
    _write(
        target / "delivery-board.md",
        "# Acceleration delivery board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "validation-commands.md",
        "# Acceleration validation commands\n\n```bash\n"
        + "\n".join(_EXECUTION_COMMANDS)
        + "\n```\n",
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
    parser = argparse.ArgumentParser(description="Acceleration closeout checks")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--ensure-doc", action="store_true")
    return parser


def build_acceleration_closeout_summary_impl(root: Path) -> dict[str, Any]:
    """Compatibility alias for legacy day-based builder name."""
    return build_acceleration_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.ensure_doc:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DEFAULT_PAGE_TEMPLATE)

    payload = build_acceleration_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/acceleration-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
