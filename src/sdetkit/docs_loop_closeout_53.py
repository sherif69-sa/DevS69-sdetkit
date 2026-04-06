from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-docs-loop-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY52_SUMMARY_PATH = "docs/artifacts/narrative-closeout-pack/narrative-closeout-summary.json"
_DAY52_BOARD_PATH = "docs/artifacts/narrative-closeout-pack/narrative-delivery-board.md"
_SECTION_HEADER = "# \u2014 Docs loop optimization closeout lane"
_REQUIRED_SECTIONS = [
    "## Why matters",
    "## Required inputs ()",
    "## command lane",
    "## Docs loop optimization contract",
    "## Docs loop quality checklist",
    "## delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit docs-loop-closeout --format json --strict",
    "python -m sdetkit docs-loop-closeout --emit-pack-dir docs/artifacts/docs-loop-closeout-pack --format json --strict",
    "python -m sdetkit docs-loop-closeout --execute --evidence-dir docs/artifacts/docs-loop-closeout-pack/evidence --format json --strict",
    "python scripts/check_docs_loop_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit docs-loop-closeout --format json --strict",
    "python -m sdetkit docs-loop-closeout --emit-pack-dir docs/artifacts/docs-loop-closeout-pack --format json --strict",
    "python scripts/check_docs_loop_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for docs-loop execution and KPI follow-up.",
    "The docs-loop lane references narrative winners and misses with deterministic cross-link remediation loops.",
    "Every section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.",
    "closeout records docs-loop learnings and re-engagement priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes wins/misses digest, proof snippet draft, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes docs-loop brief, cross-link map, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] docs-loop brief committed",
    "- [ ] docs-loop plan reviewed with owner + backup",
    "- [ ] cross-link map exported",
    "- [ ] KPI scorecard snapshot exported",
    "- [ ] re-engagement priorities drafted from learnings",
]

_DEFAULT_PAGE_TEMPLATE = """# \u2014 Docs loop optimization closeout lane

closes with a major docs loop optimization upgrade that converts narrative evidence into deterministic cross-link execution across demos, playbooks, and CLI docs.

## Why matters

- Converts narrative proof into a durable docs-loop optimization discipline.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from docs-loop upgrades into re-engagement execution.

## Required inputs ()

- `docs/artifacts/narrative-closeout-pack/narrative-closeout-summary.json`
- `docs/artifacts/narrative-closeout-pack/narrative-delivery-board.md`

## command lane

```bash
python -m sdetkit docs-loop-closeout --format json --strict
python -m sdetkit docs-loop-closeout --emit-pack-dir docs/artifacts/docs-loop-closeout-pack --format json --strict
python -m sdetkit docs-loop-closeout --execute --evidence-dir docs/artifacts/docs-loop-closeout-pack/evidence --format json --strict
python scripts/check_docs_loop_closeout_contract.py
```

## Docs loop optimization contract

- Single owner + backup reviewer are assigned for docs-loop execution and KPI follow-up.
- The docs-loop lane references narrative winners and misses with deterministic cross-link remediation loops.
- Every section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- closeout records docs-loop learnings and re-engagement priorities.

## Docs loop quality checklist

- [ ] Includes wins/misses digest, proof snippet draft, and rollback strategy
- [ ] Every section has owner, review window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes docs-loop brief, cross-link map, KPI scorecard, and execution log

## delivery board

- [ ] docs-loop brief committed
- [ ] docs-loop plan reviewed with owner + backup
- [ ] cross-link map exported
- [ ] KPI scorecard snapshot exported
- [ ] re-engagement priorities drafted from learnings

## Scoring model

weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Narrative-closeout continuity and strict baseline carryover: 35 points.
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


def _load_narrative_closeout_summary(path: Path) -> tuple[float, bool, int]:
    data_obj = _load_json(path)
    if not isinstance(data_obj, dict):
        return 0.0, False, 0
    summary_obj = data_obj.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    checks_obj = data_obj.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    score = float(summary.get("activation_score", 0.0))
    strict = coerce_bool(summary.get("strict_pass", False), default=False)
    check_count = len(checks)
    return score, strict, check_count


def _contains_all_lines(text: str, required_lines: list[str]) -> list[str]:
    return [line for line in required_lines if line not in text]


def _board_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- [")]
    return len(lines), ("" in text), ("" in text)


def build_docs_loop_closeout_summary(root: Path) -> dict[str, Any]:
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

    narrative_closeout_summary_primary = root / _DAY52_SUMMARY_PATH
    narrative_closeout_summary = narrative_closeout_summary_primary
    narrative_closeout_board_primary = root / _DAY52_BOARD_PATH
    narrative_closeout_board = narrative_closeout_board_primary
    narrative_closeout_score, narrative_closeout_strict, narrative_closeout_check_count = (
        _load_narrative_closeout_summary(narrative_closeout_summary)
    )
    board_count, board_has_previous, board_has_required = _board_stats(
        narrative_closeout_board
    )

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
            "check_id": "readme_integration_link",
            "weight": 8,
            "passed": "docs/integrations-docs-loop-closeout.md" in readme_text,
            "evidence": "docs/integrations-docs-loop-closeout.md",
        },
        {
            "check_id": "readme_command_lane",
            "weight": 4,
            "passed": "docs-loop-closeout" in readme_text,
            "evidence": "README docs-loop-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-53-big-upgrade-report.md" in docs_index_text
                and "integrations-docs-loop-closeout.md" in docs_index_text
            ),
            "evidence": "impact-53-big-upgrade-report.md + integrations-docs-loop-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ("" in top10_text and "" in top10_text),
            "evidence": "+ strategy chain",
        },
        {
            "check_id": "narrative_closeout_summary_present",
            "weight": 10,
            "passed": narrative_closeout_summary.exists(),
            "evidence": {
                "resolved": str(narrative_closeout_summary),
                "primary": str(narrative_closeout_summary_primary),
            },
        },
        {
            "check_id": "narrative_closeout_delivery_board_present",
            "weight": 8,
            "passed": narrative_closeout_board.exists(),
            "evidence": {
                "resolved": str(narrative_closeout_board),
                "primary": str(narrative_closeout_board_primary),
            },
        },
        {
            "check_id": "narrative_closeout_quality_floor",
            "weight": 10,
            "passed": narrative_closeout_strict and narrative_closeout_score >= 95,
            "evidence": {
                "narrative_closeout_score": narrative_closeout_score,
                "strict_pass": narrative_closeout_strict,
                "narrative_closeout_checks": narrative_closeout_check_count,
            },
        },
        {
            "check_id": "narrative_closeout_board_integrity",
            "weight": 7,
            "passed": board_count >= 5
            and board_has_previous
            and board_has_required,
            "evidence": {
                "board_items": board_count,
                "contains_previous": board_has_previous,
                "contains_current": board_has_required,
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
    if not narrative_closeout_summary.exists() or not narrative_closeout_board.exists():
        critical_failures.append("narrative_closeout_handoff_inputs")
    if not narrative_closeout_strict:
        critical_failures.append("narrative_closeout_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if narrative_closeout_strict:
        wins.append(
            f"Narrative-closeout continuity is strict-pass with activation score={narrative_closeout_score}."
        )
    else:
        misses.append("strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run narrative closeout command and restore strict pass baseline before lock."
        )

    if board_count >= 5 and board_has_previous and board_has_required:
        wins.append(
            f"delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "delivery board integrity is incomplete (needs >=5 items and /53 anchors)."
        )
        handoff_actions.append(
            "Repair delivery board entries to include and anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Docs-loop contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Docs-loop contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all docs-loop contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "docs-loop closeout lane is fully complete and ready for execution lane."
        )

    return {
        "name": "docs-loop-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "narrative_closeout_summary": str(narrative_closeout_summary.relative_to(root))
            if narrative_closeout_summary.exists()
            else str(narrative_closeout_summary),
            "narrative_closeout_summary_primary": str(
                narrative_closeout_summary_primary.relative_to(root)
            ),
            "narrative_closeout_delivery_board": str(narrative_closeout_board.relative_to(root))
            if narrative_closeout_board.exists()
            else str(narrative_closeout_board),
            "narrative_closeout_delivery_board_primary": str(
                narrative_closeout_board_primary.relative_to(root)
            ),
        },
        "checks": checks,
        "rollup": {
            "narrative_closeout_activation_score": narrative_closeout_score,
            "narrative_closeout_checks": narrative_closeout_check_count,
            "narrative_closeout_delivery_board_items": board_count,
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
        "Docs Loop Closeout summary (legacy: )",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- activation score: `{payload['rollup']['narrative_closeout_activation_score']}`",
        f"- checks evaluated: `{payload['rollup']['narrative_closeout_checks']}`",
        f"- delivery board checklist items: `{payload['rollup']['narrative_closeout_delivery_board_items']}`",
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
    summary_json = json.dumps(payload, indent=2) + "\n"
    summary_md = _render_text(payload) + "\n"
    _write(target / "docs-loop-closeout-summary.json", summary_json)
    _write(target / "docs-loop-closeout-summary.md", summary_md)
    # Legacy compatibility aliases
    _write(
        target / "docs-loop-brief.md",
        "# Docs-loop Brief\n\n- Objective: close with measurable docs-loop optimization gains and proof-backed cross-link quality.\n",
    )
    _write(
        target / "docs-loop-cross-link-map.csv",
        "stream,owner,backup,review_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "docs-loop-floor,qa-lead,docs-owner,2026-03-20T10:00:00Z,docs/integrations-docs-loop-closeout.md,python -m sdetkit docs-loop-closeout --format json --strict,failed-checks:0,link-drift\n",
    )
    _write(
        target / "docs-loop-kpi-scorecard.json",
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
        target / "docs-loop-execution-log.md",
        "# Execution Log\n\n- [ ] 2026-03-20: Record misses, wins, and re-engagement priorities.\n",
    )
    _write(
        target / "docs-loop-delivery-board.md",
        "# Delivery Board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "docs-loop-validation-commands.md",
        "# Validation Commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )

    # Legacy compatibility aliases


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
    summary = json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n"
    _write(evidence_path / "docs-loop-execution-summary.json", summary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Docs Loop Closeout checks")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--ensure-doc", action="store_true")
    return parser


def build_docs_loop_closeout_summary_impl(root: Path) -> dict[str, Any]:
    """Compatibility alias for legacy builder name."""
    return build_docs_loop_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.ensure_doc:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DEFAULT_PAGE_TEMPLATE)

    payload = build_docs_loop_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/docs-loop-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
