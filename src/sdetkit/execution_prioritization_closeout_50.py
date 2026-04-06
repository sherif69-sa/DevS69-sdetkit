from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-execution-prioritization-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY49_SUMMARY_PATH = (
    "docs/artifacts/weekly-review-closeout-pack-49/weekly-review-closeout-summary-49.json"
)
_DAY49_BOARD_PATH = "docs/artifacts/weekly-review-closeout-pack-49/delivery-board-49.md"
_DAY49_LEGACY_BOARD_PATH = "docs/artifacts/weekly-review-closeout-pack-49/delivery-board-49.md"
_SECTION_HEADER = '#  — Execution prioritization closeout lane'
_REQUIRED_SECTIONS = [
    '## Why  matters',
    '## Required inputs ()',
    '##  command lane',
    "## Execution prioritization closeout contract",
    "## Execution prioritization quality checklist",
    '##  delivery board',
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit execution-prioritization-closeout --format json --strict",
    "python -m sdetkit execution-prioritization-closeout --emit-pack-dir docs/artifacts/execution-prioritization-closeout-pack --format json --strict",
    "python -m sdetkit execution-prioritization-closeout --execute --evidence-dir docs/artifacts/execution-prioritization-closeout-pack/evidence --format json --strict",
    "python scripts/check_execution_prioritization_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit execution-prioritization-closeout --format json --strict",
    "python -m sdetkit execution-prioritization-closeout --emit-pack-dir docs/artifacts/execution-prioritization-closeout-pack --format json --strict",
    "python scripts/check_execution_prioritization_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    'Single owner + backup reviewer are assigned for  execution prioritization execution and KPI follow-up.',
    'The  execution prioritization lane references  weekly-review winners and misses with deterministic execution-board loops.',
    'Every  section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.',
    ' closeout records execution-board learnings and  release priorities.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes wins/misses digest, risk register, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes execution brief, risk map, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  execution prioritization brief committed',
    '- [ ]  priorities reviewed with owner + backup',
    '- [ ]  risk register exported',
    '- [ ]  KPI scorecard snapshot exported',
    '- [ ]  release priorities drafted from  learnings',
]

_DEFAULT_PAGE_TEMPLATE = '#  — Execution prioritization closeout lane\n\n closes with a major execution-prioritization upgrade that converts  weekly-review evidence into a deterministic execution board and release-storytelling handoff.\n\n## Why  matters\n\n- Converts  weekly-review proof into execution-board discipline.\n- Protects quality with owner accountability, command proof, and KPI guardrails.\n- Produces a deterministic handoff from execution priorities into  storytelling priorities.\n\n## Required inputs ()\n\n- `docs/artifacts/weekly-review-closeout-pack-49/weekly-review-closeout-summary-49.json`\n- `docs/artifacts/weekly-review-closeout-pack-49/delivery-board-49.md`\n\n##  command lane\n\n```bash\npython -m sdetkit execution-prioritization-closeout --format json --strict\npython -m sdetkit execution-prioritization-closeout --emit-pack-dir docs/artifacts/execution-prioritization-closeout-pack --format json --strict\npython -m sdetkit execution-prioritization-closeout --execute --evidence-dir docs/artifacts/execution-prioritization-closeout-pack/evidence --format json --strict\npython scripts/check_execution_prioritization_closeout_contract.py\n```\n\n## Execution prioritization closeout contract\n\n- Single owner + backup reviewer are assigned for  execution prioritization execution and KPI follow-up.\n- The  execution prioritization lane references  weekly-review winners and misses with deterministic execution-board loops.\n- Every  section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.\n-  closeout records execution-board learnings and  release priorities.\n\n## Execution prioritization quality checklist\n\n- [ ] Includes wins/misses digest, risk register, and rollback strategy\n- [ ] Every section has owner, review window, KPI target, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI\n- [ ] Artifact pack includes execution brief, risk map, KPI scorecard, and execution log\n\n##  delivery board\n\n- [ ]  execution prioritization brief committed\n- [ ]  priorities reviewed with owner + backup\n- [ ]  risk register exported\n- [ ]  KPI scorecard snapshot exported\n- [ ]  release priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Docs contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 35 points.\n- Execution prioritization contract lock + delivery board readiness: 15 points.\n'


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


def _load_cycle49(path: Path) -> tuple[float, bool, int]:
    data = _load_json(path)
    if data is None:
        return 0.0, False, 0
    summary = data.get("summary")
    checks = data.get("checks")
    if not isinstance(summary, dict):
        return 0.0, False, 0
    score = float(summary.get("activation_score", 0.0))
    strict = coerce_bool(summary.get("strict_pass", False), default=False)
    check_count = len(checks) if isinstance(checks, list) else 0
    return score, strict, check_count


def _contains_all_lines(text: str, required_lines: list[str]) -> list[str]:
    return [line for line in required_lines if line not in text]


def _resolve_existing_path(root: Path, primary: str, legacy: str) -> Path:
    primary_path = root / primary
    if primary_path.exists():
        return primary_path
    return root / legacy


def _board_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- [")]
    return len(lines), ('' in text), ('' in text)


def build_execution_prioritization_closeout_summary(root: Path) -> dict[str, Any]:
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

    summary = root / _DAY49_SUMMARY_PATH
    board = _resolve_existing_path(root, _DAY49_BOARD_PATH, _DAY49_LEGACY_BOARD_PATH)
    score, strict, check_count = _load_cycle49(summary)
    board_count, board_has_cycle49, board_has_cycle50 = _board_stats(board)

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
            "passed": "docs/integrations-execution-prioritization-closeout.md" in readme_text,
            "evidence": "docs/integrations-execution-prioritization-closeout.md",
        },
        {
            "check_id": "readme_execution_prioritization_command",
            "weight": 4,
            "passed": "execution-prioritization-closeout" in readme_text,
            "evidence": "execution-prioritization-closeout",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-50-big-upgrade-report.md" in docs_index_text
                and "integrations-execution-prioritization-closeout.md" in docs_index_text
            ),
            "evidence": "impact-50-big-upgrade-report.md + integrations-execution-prioritization-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ('' in top10_text and '' in top10_text),
            "evidence": ' +  strategy chain',
        },
        {
            "check_id": "summary_present",
            "weight": 10,
            "passed": summary.exists(),
            "evidence": str(summary),
        },
        {
            "check_id": "delivery_board_present",
            "weight": 8,
            "passed": board.exists(),
            "evidence": str(board),
        },
        {
            "check_id": "quality_floor",
            "weight": 10,
            "passed": strict and score >= 95,
            "evidence": {
                "score": score,
                "strict_pass": strict,
                "checks": check_count,
            },
        },
        {
            "check_id": "board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_cycle49 and board_has_cycle50,
            "evidence": {
                "board_items": board_count,
                "contains": board_has_cycle49,
                "contains": board_has_cycle50,
            },
        },
        {
            "check_id": "execution_prioritization_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "execution_prioritization_quality_checklist_locked",
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
    if not summary.exists() or not board.exists():
        critical_failures.append("handoff_inputs")
    if not strict:
        critical_failures.append("strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if strict:
        wins.append(f"49 continuity is strict-pass with activation score={score}.")
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  weekly review closeout command and restore strict pass baseline before  lock.'
        )

    if board_count >= 5 and board_has_cycle49 and board_has_cycle50:
        wins.append(
            f"49 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and /50 anchors).'
        )
        handoff_actions.append(
            'Repair  delivery board entries to include  and  anchors.'
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Execution prioritization contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Execution prioritization contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            'Complete all  execution prioritization contract lines, quality checklist entries, and delivery board tasks in docs.'
        )

    if not failed and not critical_failures:
        wins.append(
            ' execution prioritization closeout lane is fully complete and ready for  execution lane.'
        )

    return {
        "name": "execution-prioritization-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "summary": str(summary.relative_to(root))
            if summary.exists()
            else str(summary),
            "delivery_board": str(board.relative_to(root))
            if board.exists()
            else str(board),
        },
        "checks": checks,
        "rollup": {
            "activation_score": score,
            "checks": check_count,
            "delivery_board_items": board_count,
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
        ' execution prioritization closeout summary',
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- 49 activation score: `{payload['rollup']['activation_score']}`",
        f"- 49 checks evaluated: `{payload['rollup']['checks']}`",
        f"- 49 delivery board checklist items: `{payload['rollup']['delivery_board_items']}`",
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
    _write(
        target / "execution-prioritization-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "execution-prioritization-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "execution-prioritization-brief.md",
        '#  Execution Prioritization Brief\n\n- Objective: close  with measurable execution-board discipline and prioritized release storytelling gains.\n',
    )
    _write(
        target / "execution-prioritization-risk-register.csv",
        "stream,owner,backup,review_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "execution-prioritization-floor,qa-lead,docs-owner,2026-03-18T10:00:00Z,docs/integrations-execution-prioritization-closeout.md,python -m sdetkit execution-prioritization-closeout --format json --strict,failed-checks:0,priority-drift\n",
    )
    _write(
        target / "execution-prioritization-kpi-scorecard.json",
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
        target / "execution-prioritization-execution-log.md",
        '#  Execution Log\n\n- [ ] 2026-03-18: Record misses, wins, and  release priorities.\n',
    )
    _write(
        target / "execution-prioritization-delivery-board.md",
        '#  Delivery Board\n\n' + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "execution-prioritization-validation-commands.md",
        '#  Validation Commands\n\n```bash\n' + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        evidence_path / "execution-prioritization-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execution prioritization closeout checks (legacy alias: cycle50-execution-prioritization-closeout)"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--ensure-doc", action="store_true")
    return parser


def build_execution_prioritization_closeout_summary_impl(root: Path) -> dict[str, Any]:
    'Compatibility alias for legacy -based builder name.'
    return build_execution_prioritization_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.ensure_doc:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DEFAULT_PAGE_TEMPLATE)

    payload = build_execution_prioritization_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/execution-prioritization-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
