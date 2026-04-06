from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-phase3-kickoff-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY60_SUMMARY_PATH = (
    "docs/artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-closeout-summary.json"
)
_DAY60_BOARD_PATH = (
    "docs/artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-delivery-board.md"
)
_SECTION_HEADER = "# \u2014 Phase-3 kickoff execution closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Phase3 Kickoff Closeout matters",
    "## Required inputs ()",
    "## Phase3 Kickoff Closeout command lane",
    "## Phase-3 kickoff execution contract",
    "## Phase-3 kickoff quality checklist",
    "## Phase3 Kickoff Closeout delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit phase3-kickoff-closeout --format json --strict",
    "python -m sdetkit phase3-kickoff-closeout --emit-pack-dir docs/artifacts/phase3-kickoff-closeout-pack --format json --strict",
    "python -m sdetkit phase3-kickoff-closeout --execute --evidence-dir docs/artifacts/phase3-kickoff-closeout-pack/evidence --format json --strict",
    "python scripts/check_phase3_kickoff_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit phase3-kickoff-closeout --format json --strict",
    "python -m sdetkit phase3-kickoff-closeout --emit-pack-dir docs/artifacts/phase3-kickoff-closeout-pack --format json --strict",
    "python scripts/check_phase3_kickoff_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Phase-3 kickoff execution and trust-signal triage.",
    "The lane references Phase-2 wrap outcomes, risks, and KPI continuity evidence.",
    "Every section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "closeout records Phase-3 baseline activation, trust KPI owners, and community program priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes baseline snapshot, owner map, KPI guardrails, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each trust KPI",
    "- [ ] Artifact pack includes kickoff brief, trust ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Phase-3 kickoff brief committed",
    "- [ ] kickoff reviewed with owner + backup",
    "- [ ] trust ledger exported",
    "- [ ] KPI scorecard snapshot exported",
    "- [ ] community program priorities drafted from learnings",
]

_DEFAULT_PAGE_TEMPLATE = """# \u2014 Phase-3 kickoff execution closeout lane

ships a major Phase-3 kickoff upgrade that converts wrap evidence into a strict baseline for ecosystem + trust execution.

## Why Phase3 Kickoff Closeout matters

- Converts closeout evidence into repeatable Phase-3 execution loops.
- Protects trust outcomes with ownership, command proof, and KPI rollback guardrails.
- Produces a deterministic handoff from kickoff into community program setup.

## Required inputs ()

- `docs/artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-closeout-summary.json`
- `docs/artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-delivery-board.md`

## Phase3 Kickoff Closeout command lane

```bash
python -m sdetkit phase3-kickoff-closeout --format json --strict
python -m sdetkit phase3-kickoff-closeout --emit-pack-dir docs/artifacts/phase3-kickoff-closeout-pack --format json --strict
python -m sdetkit phase3-kickoff-closeout --execute --evidence-dir docs/artifacts/phase3-kickoff-closeout-pack/evidence --format json --strict
python scripts/check_phase3_kickoff_closeout_contract.py
```

## Phase-3 kickoff execution contract

- Single owner + backup reviewer are assigned for Phase-3 kickoff execution and trust-signal triage.
- The lane references Phase-2 wrap outcomes, risks, and KPI continuity evidence.
- Every section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- closeout records Phase-3 baseline activation, trust KPI owners, and community program priorities.

## Phase-3 kickoff quality checklist

- [ ] Includes baseline snapshot, owner map, KPI guardrails, and rollback strategy
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each trust KPI
- [ ] Artifact pack includes kickoff brief, trust ledger, KPI scorecard, and execution log

## Phase3 Kickoff Closeout delivery board

- [ ] Phase-3 kickoff brief committed
- [ ] kickoff reviewed with owner + backup
- [ ] trust ledger exported
- [ ] KPI scorecard snapshot exported
- [ ] community program priorities drafted from learnings

## Scoring model

weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Phase2-wrap-handoff continuity and strict baseline carryover: 35 points.
- Phase-3 kickoff contract lock + delivery board readiness: 15 points.
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


def _load_phase2_wrap_handoff_summary(path: Path) -> tuple[int, bool, int]:
    payload_obj = _load_json(path)
    if not isinstance(payload_obj, dict):
        return 0, False, 0
    summary_obj = payload_obj.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    score = int(summary.get("activation_score", 0))
    strict = coerce_bool(summary.get("strict_pass", False), default=False)
    checks_obj = payload_obj.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    return score, strict, len(checks)


def _count_board_items(path: Path, needle: str) -> tuple[int, bool]:
    text = _read(path)
    lines = [ln.strip() for ln in text.splitlines()]
    checks = [ln for ln in lines if ln.startswith("- [")]
    return len(checks), (needle in text)


def build_phase3_kickoff_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)

    phase2_wrap_handoff_summary = root / _DAY60_SUMMARY_PATH
    phase2_wrap_handoff_board = root / _DAY60_BOARD_PATH
    phase2_wrap_handoff_score, phase2_wrap_handoff_strict, phase2_wrap_handoff_check_count = (
        _load_phase2_wrap_handoff_summary(phase2_wrap_handoff_summary)
    )
    board_count, board_has_required = _count_board_items(
        phase2_wrap_handoff_board, ""
    )

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_command_lane",
            "weight": 7,
            "passed": ("phase3-kickoff-closeout" in readme_text),
            "evidence": "README phase3-kickoff-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-61-big-upgrade-report.md" in docs_index_text
                and "integrations-phase3-kickoff-closeout.md" in docs_index_text
            ),
            "evidence": "impact-61-big-upgrade-report.md + integrations-phase3-kickoff-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ("" in top10_text and "" in top10_text),
            "evidence": "+ strategy chain",
        },
        {
            "check_id": "phase2_wrap_handoff_summary_present",
            "weight": 10,
            "passed": phase2_wrap_handoff_summary.exists(),
            "evidence": str(phase2_wrap_handoff_summary),
        },
        {
            "check_id": "phase2_wrap_handoff_delivery_board_present",
            "weight": 8,
            "passed": phase2_wrap_handoff_board.exists(),
            "evidence": str(phase2_wrap_handoff_board),
        },
        {
            "check_id": "phase2_wrap_handoff_quality_floor",
            "weight": 15,
            "passed": phase2_wrap_handoff_strict and phase2_wrap_handoff_score >= 95,
            "evidence": {
                "phase2_wrap_handoff_score": phase2_wrap_handoff_score,
                "strict_pass": phase2_wrap_handoff_strict,
                "phase2_wrap_handoff_checks": phase2_wrap_handoff_check_count,
            },
        },
        {
            "check_id": "phase2_wrap_handoff_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_required,
            "evidence": {
                "board_items": board_count,
                "contains_required": board_has_required,
            },
        },
        {
            "check_id": "page_header",
            "weight": 7,
            "passed": _SECTION_HEADER in page_text,
            "evidence": _SECTION_HEADER,
        },
        {
            "check_id": "required_sections",
            "weight": 10,
            "passed": not missing_sections,
            "evidence": missing_sections or "all sections present",
        },
        {
            "check_id": "required_commands",
            "weight": 8,
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
            "weight": 3,
            "passed": not missing_quality_lines,
            "evidence": missing_quality_lines or "quality checklist locked",
        },
        {
            "check_id": "delivery_board_lock",
            "weight": 2,
            "passed": not missing_board_items,
            "evidence": missing_board_items or "delivery board locked",
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not phase2_wrap_handoff_summary.exists() or not phase2_wrap_handoff_board.exists():
        critical_failures.append("phase2_wrap_handoff_handoff_inputs")
    if not phase2_wrap_handoff_strict:
        critical_failures.append("phase2_wrap_handoff_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if phase2_wrap_handoff_strict:
        wins.append(
            f"Phase2-wrap-handoff continuity is strict-pass with activation score={phase2_wrap_handoff_score}."
        )
    else:
        misses.append("strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Phase-2 wrap + handoff closeout command and restore strict baseline before lock."
        )

    if board_count >= 5 and board_has_required:
        wins.append(
            f"delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "delivery board integrity is incomplete (needs >=5 items and anchors)."
        )
        handoff_actions.append("Repair delivery board entries to include anchors.")

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Phase-3 kickoff contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Phase-3 kickoff contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Phase-3 kickoff closeout lane is fully complete and ready for community execution lane."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "phase3-kickoff-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "phase2_wrap_handoff_summary": str(phase2_wrap_handoff_summary.relative_to(root))
            if phase2_wrap_handoff_summary.exists()
            else str(phase2_wrap_handoff_summary),
            "phase2_wrap_handoff_delivery_board": str(phase2_wrap_handoff_board.relative_to(root))
            if phase2_wrap_handoff_board.exists()
            else str(phase2_wrap_handoff_board),
        },
        "checks": checks,
        "rollup": {
            "phase2_wrap_handoff_activation_score": phase2_wrap_handoff_score,
            "phase2_wrap_handoff_checks": phase2_wrap_handoff_check_count,
            "phase2_wrap_handoff_delivery_board_items": board_count,
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
        "Phase3 Kickoff Closeout summary",
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
        target / "phase3-kickoff-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "phase3-kickoff-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "phase3-kickoff-brief.md", "# Phase-3 kickoff brief\n")
    _write(target / "phase3-kickoff-trust-ledger.csv", "risk,owner,mitigation,status\n")
    _write(target / "phase3-kickoff-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "phase3-kickoff-execution-log.md", "# execution log\n")
    _write(
        target / "phase3-kickoff-delivery-board.md",
        "\n".join(["# delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "phase3-kickoff-validation-commands.md",
        "# validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "phase3-kickoff-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_phase3_kickoff_closeout_summary_impl(root: Path) -> dict[str, Any]:
    """Compatibility alias for legacy builder name."""
    return build_phase3_kickoff_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase-3 kickoff closeout checks")
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
        _write(root / _PAGE_PATH, _DEFAULT_PAGE_TEMPLATE)

    payload = build_phase3_kickoff_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/phase3-kickoff-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
