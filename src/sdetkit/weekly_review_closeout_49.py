from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-weekly-review-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY48_SUMMARY_PATH = "docs/artifacts/objection-closeout-pack-48/objection-closeout-summary-48.json"
_DAY48_BOARD_PATH = "docs/artifacts/objection-closeout-pack-48/delivery-board-48.md"
_DAY48_LEGACY_SUMMARY_PATH = (
    "docs/artifacts/objection-closeout-pack/objection-closeout-summary.json"
)
_DAY48_LEGACY_BOARD_PATH = "docs/artifacts/objection-closeout-pack/objection-delivery-board.md"
_SECTION_HEADER = '#  — Weekly review closeout lane'
_REQUIRED_SECTIONS = [
    '## Why  matters',
    '## Required inputs ()',
    '##  command lane',
    "## Weekly review closeout contract",
    "## Weekly review quality checklist",
    '##  delivery board',
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit weekly-review-closeout --format json --strict",
    "python -m sdetkit weekly-review-closeout --emit-pack-dir docs/artifacts/weekly-review-closeout-pack --format json --strict",
    "python -m sdetkit weekly-review-closeout --execute --evidence-dir docs/artifacts/weekly-review-closeout-pack/evidence --format json --strict",
    "python scripts/check_weekly_review_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit weekly-review-closeout --format json --strict",
    "python -m sdetkit weekly-review-closeout --emit-pack-dir docs/artifacts/weekly-review-closeout-pack --format json --strict",
    "python scripts/check_weekly_review_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    'Single owner + backup reviewer are assigned for  weekly review execution and KPI follow-up.',
    'The  weekly review lane references  objection winners and misses with deterministic prioritization loops.',
    'Every  section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.',
    ' closeout records weekly-review learnings and  execution priorities.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes wins/misses digest, risk register, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes review brief, risk map, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  weekly review brief committed',
    '- [ ]  priorities reviewed with owner + backup',
    '- [ ]  risk register exported',
    '- [ ]  KPI scorecard snapshot exported',
    '- [ ]  execution priorities drafted from  learnings',
]

_DEFAULT_PAGE_TEMPLATE = '#  — Weekly review closeout lane\n\n closes with a major weekly-review upgrade that converts  objection evidence into deterministic prioritization and handoff loops.\n\n## Why  matters\n\n- Converts  objection proof into weekly review execution discipline.\n- Protects quality with owner accountability, command proof, and KPI guardrails.\n- Produces a deterministic handoff from weekly-review outcomes into  execution priorities.\n\n## Required inputs ()\n\n- `docs/artifacts/objection-closeout-pack-48/objection-closeout-summary-48.json`\n- `docs/artifacts/objection-closeout-pack-48/delivery-board-48.md`\n\n##  command lane\n\n```bash\npython -m sdetkit weekly-review-closeout --format json --strict\npython -m sdetkit weekly-review-closeout --emit-pack-dir docs/artifacts/weekly-review-closeout-pack --format json --strict\npython -m sdetkit weekly-review-closeout --execute --evidence-dir docs/artifacts/weekly-review-closeout-pack/evidence --format json --strict\npython scripts/check_weekly_review_closeout_contract.py\n```\n\n## Weekly review closeout contract\n\n- Single owner + backup reviewer are assigned for  weekly review execution and KPI follow-up.\n- The  weekly review lane references  objection winners and misses with deterministic prioritization loops.\n- Every  section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.\n-  closeout records weekly-review learnings and  execution priorities.\n\n## Weekly review quality checklist\n\n- [ ] Includes wins/misses digest, risk register, and rollback strategy\n- [ ] Every section has owner, review window, KPI target, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI\n- [ ] Artifact pack includes review brief, risk map, KPI scorecard, and execution log\n\n##  delivery board\n\n- [ ]  weekly review brief committed\n- [ ]  priorities reviewed with owner + backup\n- [ ]  risk register exported\n- [ ]  KPI scorecard snapshot exported\n- [ ]  execution priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Docs contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 35 points.\n- Weekly review contract lock + delivery board readiness: 15 points.\n'


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


def _load_cycle48(path: Path) -> tuple[float, bool, int]:
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


def _resolve_existing_path(root: Path, primary: str, legacy: str) -> Path:
    primary_path = root / primary
    if primary_path.exists():
        return primary_path
    return root / legacy


def build_weekly_review_closeout_summary(root: Path) -> dict[str, Any]:
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

    summary = _resolve_existing_path(root, _DAY48_SUMMARY_PATH, _DAY48_LEGACY_SUMMARY_PATH)
    board = _resolve_existing_path(root, _DAY48_BOARD_PATH, _DAY48_LEGACY_BOARD_PATH)
    score, strict, check_count = _load_cycle48(summary)
    board_count, board_has_cycle48, board_has_cycle49 = _board_stats(board)

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
            "passed": "docs/integrations-weekly-review-closeout.md" in readme_text,
            "evidence": "docs/integrations-weekly-review-closeout.md",
        },
        {
            "check_id": "readme_command_lane",
            "weight": 4,
            "passed": "weekly-review-closeout" in readme_text,
            "evidence": "weekly-review-closeout",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-49-big-upgrade-report.md" in docs_index_text
                and "integrations-weekly-review-closeout.md" in docs_index_text
            ),
            "evidence": "impact-49-big-upgrade-report.md + integrations-weekly-review-closeout.md",
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
            "passed": board_count >= 5 and board_has_cycle48 and board_has_cycle49,
            "evidence": {
                "board_items": board_count,
                "contains": board_has_cycle48,
                "contains": board_has_cycle49,
            },
        },
        {
            "check_id": "weekly_review_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "weekly_review_quality_checklist_locked",
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
        wins.append(f"48 continuity is strict-pass with activation score={score}.")
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  objection closeout command and restore strict pass baseline before  lock.'
        )

    if board_count >= 5 and board_has_cycle48 and board_has_cycle49:
        wins.append(
            f"48 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and /49 anchors).'
        )
        handoff_actions.append(
            'Repair  delivery board entries to include  and  anchors.'
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Weekly review execution contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Weekly review contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            'Complete all  weekly review contract lines, quality checklist entries, and delivery board tasks in docs.'
        )

    if not failed and not critical_failures:
        wins.append(
            ' advanced weekly review control tower is fully complete and ready for  execution lane.'
        )

    return {
        "name": "weekly-review-closeout",
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
        ' advanced weekly review control tower summary',
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- 48 activation score: `{payload['rollup']['activation_score']}`",
        f"- 48 checks evaluated: `{payload['rollup']['checks']}`",
        f"- 48 delivery board checklist items: `{payload['rollup']['delivery_board_items']}`",
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
    _write(target / "weekly-review-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "weekly-review-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "weekly-review-brief-49.md",
        '#  Weekly Review Brief\n\n- Objective: close  with measurable weekly-review discipline and prioritized execution gains.\n',
    )
    _write(
        target / "weekly-review-risk-register-49.csv",
        "stream,owner,backup,review_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "weekly-review-floor,qa-lead,docs-owner,2026-03-17T10:00:00Z,docs/integrations-weekly-review-closeout.md,python -m sdetkit weekly-review-closeout --format json --strict,failed-checks:0,priority-drift\n",
    )
    _write(
        target / "weekly-review-kpi-scorecard-49.json",
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
        target / "advanced-priority-matrix-49.json",
        json.dumps(
            {
                "priority_model": "weighted-weekly-review",
                "inputs": {
                    "passed_checks": payload["summary"]["passed_checks"],
                    "failed_checks": payload["summary"]["failed_checks"],
                    "critical_failures": payload["summary"]["critical_failures"],
                },
                "priorities": [
                    {
                        "lane": "stability",
                        "score": max(0, 100 - payload["summary"]["failed_checks"] * 10),
                    },
                    {
                        "lane": "delivery",
                        "score": max(0, 100 - len(payload["summary"]["critical_failures"]) * 25),
                    },
                ],
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "execution-log-49.md",
        '#  Execution Log\n\n- [ ] 2026-03-17: Record misses, wins, and  execution priorities.\n',
    )
    _write(
        target / "weekly-review-delivery-board.md",
        '#  Delivery Board\n\n' + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "delivery-board-49.md",
        '#  Delivery Board\n\n' + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "validation-commands-49.md",
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
        evidence_path / "weekly-review-execution-summary-49.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Weekly review closeout checks")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--ensure-doc", action="store_true")
    return parser


def build_weekly_review_closeout_summary_impl(root: Path) -> dict[str, Any]:
    'Compatibility alias for legacy -based builder name.'
    return build_weekly_review_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.ensure_doc:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DEFAULT_PAGE_TEMPLATE)

    payload = build_weekly_review_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/weekly-review-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
