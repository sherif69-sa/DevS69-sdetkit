from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-optimization-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY45_SUMMARY_PATH = "docs/artifacts/expansion-closeout-pack/expansion-closeout-summary.json"
_DAY45_BOARD_PATH = "docs/artifacts/expansion-closeout-pack/expansion-delivery-board.md"
_SECTION_HEADER = '#  — Optimization closeout lane'
_REQUIRED_SECTIONS = [
    '## Why  matters',
    '## Required inputs ()',
    '##  command lane',
    "## Optimization closeout contract",
    "## Optimization quality checklist",
    '##  delivery board',
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit optimization-closeout --format json --strict",
    "python -m sdetkit optimization-closeout --emit-pack-dir docs/artifacts/optimization-closeout-pack --format json --strict",
    "python -m sdetkit optimization-closeout --execute --evidence-dir docs/artifacts/optimization-closeout-pack/evidence --format json --strict",
    "python scripts/check_optimization_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit optimization-closeout --format json --strict",
    "python -m sdetkit optimization-closeout --emit-pack-dir docs/artifacts/optimization-closeout-pack --format json --strict",
    "python scripts/check_optimization_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    'Single owner + backup reviewer are assigned for  optimization lane execution and KPI follow-up.',
    'The  optimization lane references  expansion winners and misses with deterministic optimization loops.',
    'Every  section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.',
    ' closeout records optimization learnings and  reliability priorities.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes optimization summary, bottleneck map, and rollback strategy",
    "- [ ] Every section has owner, publish window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes optimization plan, bottleneck map, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  optimization plan draft committed',
    '- [ ]  review notes captured with owner + backup',
    '- [ ]  bottleneck map exported',
    '- [ ]  KPI scorecard snapshot exported',
    '- [ ]  reliability priorities drafted from  learnings',
]

_DEFAULT_PAGE_TEMPLATE = '#  — Optimization closeout lane\n\n closes with a major optimization upgrade that converts  expansion evidence into deterministic improvement loops.\n\n## Why  matters\n\n- Converts  expansion proof into optimization-first operating motion.\n- Protects quality with owner accountability, command proof, and KPI guardrails.\n- Produces a deterministic handoff from optimization outcomes into  reliability priorities.\n\n## Required inputs ()\n\n- `docs/artifacts/expansion-closeout-pack/expansion-closeout-summary.json`\n- `docs/artifacts/expansion-closeout-pack/expansion-delivery-board.md`\n\n##  command lane\n\n```bash\npython -m sdetkit optimization-closeout --format json --strict\npython -m sdetkit optimization-closeout --emit-pack-dir docs/artifacts/optimization-closeout-pack --format json --strict\npython -m sdetkit optimization-closeout --execute --evidence-dir docs/artifacts/optimization-closeout-pack/evidence --format json --strict\npython scripts/check_optimization_closeout_contract.py\n```\n\n## Optimization closeout contract\n\n- Single owner + backup reviewer are assigned for  optimization lane execution and KPI follow-up.\n- The  optimization lane references  expansion winners and misses with deterministic optimization loops.\n- Every  section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.\n-  closeout records optimization learnings and  reliability priorities.\n\n## Optimization quality checklist\n\n- [ ] Includes optimization summary, bottleneck map, and rollback strategy\n- [ ] Every section has owner, publish window, KPI target, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI\n- [ ] Artifact pack includes optimization plan, bottleneck map, KPI scorecard, and execution log\n\n##  delivery board\n\n- [ ]  optimization plan draft committed\n- [ ]  review notes captured with owner + backup\n- [ ]  bottleneck map exported\n- [ ]  KPI scorecard snapshot exported\n- [ ]  reliability priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Docs contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 35 points.\n- Optimization contract lock + delivery board readiness: 15 points.\n'


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


def _load_expansion_closeout(path: Path) -> tuple[float, bool, int]:
    data = _load_json(path)
    if data is None:
        return 0.0, False, 0
    summary = data.get("summary")
    checks = data.get("checks")
    score = summary.get("activation_score") if isinstance(summary, dict) else None
    strict_pass = summary.get("strict_pass") if isinstance(summary, dict) else False
    count = len(checks) if isinstance(checks, list) else 0
    return float(score or 0.0), bool(strict_pass), count


def _board_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    items = [line for line in text.splitlines() if line.strip().startswith("- [")]
    return len(items), '' in text, '' in text


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_optimization_closeout_summary(root: Path) -> dict[str, Any]:
    readme_path = "README.md"
    docs_index_path = "docs/index.md"
    docs_page_path = _PAGE_PATH
    top10_path = _TOP10_PATH

    readme_text = _read(root / readme_path)
    docs_index_text = _read(root / docs_index_path)
    page_path = root / docs_page_path
    page_text = _read(page_path)
    top10_text = _read(root / top10_path)

    missing_sections = [s for s in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if s not in page_text]
    missing_commands = [c for c in _REQUIRED_COMMANDS if c not in page_text]
    missing_contract_lines = _contains_all_lines(
        page_text, [f"- {line}" for line in _REQUIRED_CONTRACT_LINES]
    )
    missing_quality_lines = _contains_all_lines(page_text, _REQUIRED_QUALITY_LINES)
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    expansion_closeout_summary = root / _DAY45_SUMMARY_PATH
    expansion_closeout_board = root / _DAY45_BOARD_PATH
    expansion_closeout_score, expansion_closeout_strict, expansion_closeout_check_count = (
        _load_expansion_closeout(expansion_closeout_summary)
    )
    board_count, board_has_expansion_closeout, board_has_optimization_closeout = _board_stats(
        expansion_closeout_board
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
            "passed": "docs/integrations-optimization-closeout.md" in readme_text,
            "evidence": "docs/integrations-optimization-closeout.md",
        },
        {
            "check_id": "readme_command_lane",
            "weight": 4,
            "passed": "optimization-closeout" in readme_text,
            "evidence": "optimization-closeout",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-46-big-upgrade-report.md" in docs_index_text
                and "integrations-optimization-closeout.md" in docs_index_text
            ),
            "evidence": "impact-46-big-upgrade-report.md + integrations-optimization-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ('' in top10_text and '' in top10_text),
            "evidence": ' +  strategy chain',
        },
        {
            "check_id": "expansion_closeout_summary_present",
            "weight": 10,
            "passed": expansion_closeout_summary.exists(),
            "evidence": str(expansion_closeout_summary),
        },
        {
            "check_id": "expansion_closeout_delivery_board_present",
            "weight": 8,
            "passed": expansion_closeout_board.exists(),
            "evidence": str(expansion_closeout_board),
        },
        {
            "check_id": "expansion_closeout_quality_floor",
            "weight": 10,
            "passed": expansion_closeout_strict and expansion_closeout_score >= 95,
            "evidence": {
                "expansion_closeout_score": expansion_closeout_score,
                "strict_pass": expansion_closeout_strict,
                "expansion_closeout_checks": expansion_closeout_check_count,
            },
        },
        {
            "check_id": "expansion_closeout_board_integrity",
            "weight": 7,
            "passed": board_count >= 5
            and board_has_expansion_closeout
            and board_has_optimization_closeout,
            "evidence": {
                "board_items": board_count,
                "contains_expansion_closeout": board_has_expansion_closeout,
                "contains_optimization_closeout": board_has_optimization_closeout,
            },
        },
        {
            "check_id": "optimization_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "optimization_quality_checklist_locked",
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
    if not expansion_closeout_summary.exists() or not expansion_closeout_board.exists():
        critical_failures.append("expansion_closeout_handoff_inputs")
    if not expansion_closeout_strict:
        critical_failures.append("expansion_closeout_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if expansion_closeout_strict:
        wins.append(
            f"45 continuity is strict-pass with activation score={expansion_closeout_score}."
        )
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  expansion closeout command and restore strict pass baseline before  lock.'
        )

    if board_count >= 5 and board_has_expansion_closeout and board_has_optimization_closeout:
        wins.append(
            f"45 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and /46 anchors).'
        )
        handoff_actions.append(
            'Repair  delivery board entries to include  and  anchors.'
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Optimization execution contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Optimization contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            'Complete all  optimization contract lines, quality checklist entries, and delivery board tasks in docs.'
        )

    if not failed and not critical_failures:
        wins.append(
            ' optimization closeout lane is fully complete and ready for  reliability lane.'
        )

    return {
        "name": "optimization-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "expansion_closeout_summary": str(expansion_closeout_summary.relative_to(root))
            if expansion_closeout_summary.exists()
            else str(expansion_closeout_summary),
            "expansion_closeout_delivery_board": str(expansion_closeout_board.relative_to(root))
            if expansion_closeout_board.exists()
            else str(expansion_closeout_board),
        },
        "checks": checks,
        "rollup": {
            "expansion_closeout_activation_score": expansion_closeout_score,
            "expansion_closeout_checks": expansion_closeout_check_count,
            "expansion_closeout_delivery_board_items": board_count,
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
        ' optimization closeout summary',
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- 45 activation score: `{payload['rollup']['expansion_closeout_activation_score']}`",
        f"- 45 checks evaluated: `{payload['rollup']['expansion_closeout_checks']}`",
        f"- 45 delivery board checklist items: `{payload['rollup']['expansion_closeout_delivery_board_items']}`",
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
    _write(target / "optimization-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "optimization-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "optimization-plan.md",
        '#  Optimization Plan\n\n- Objective: close  with measurable efficiency and quality gains.\n',
    )
    _write(
        target / "optimization-bottleneck-map.csv",
        "stream,owner,backup,publish_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "optimization-floor,qa-lead,platform-owner,2026-03-14T10:00:00Z,docs/integrations-optimization-closeout.md,python -m sdetkit optimization-closeout --format json --strict,failed-checks:0,reliability-drift\n",
    )
    _write(
        target / "optimization-kpi-scorecard.json",
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
        target / "optimization-execution-log.md",
        '#  Execution Log\n\n- [ ] 2026-03-13: Record misses, wins, and  reliability priorities.\n',
    )
    _write(
        target / "optimization-delivery-board.md",
        '#  Delivery Board\n\n' + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "optimization-validation-commands.md",
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
        evidence_path / "optimization-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=' optimization closeout checks')
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--ensure-doc", action="store_true")
    return parser


def build_optimization_closeout_summary_impl(root: Path) -> dict[str, Any]:
    'Compatibility alias for legacy -based builder name.'
    return build_optimization_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.ensure_doc:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DEFAULT_PAGE_TEMPLATE)

    payload = build_optimization_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/optimization-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
