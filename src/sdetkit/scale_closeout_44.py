from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-scale-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY43_SUMMARY_PATH = (
    "docs/artifacts/acceleration-closeout-pack-43/acceleration-closeout-summary-43.json"
)
_DAY43_BOARD_PATH = "docs/artifacts/acceleration-closeout-pack-43/delivery-board-43.md"
_DAY43_LEGACY_SUMMARY_PATH = (
    "docs/artifacts/acceleration-closeout-pack/acceleration-closeout-summary.json"
)
_DAY43_LEGACY_BOARD_PATH = "docs/artifacts/acceleration-closeout-pack/delivery-board.md"
_SECTION_HEADER = '#  — Scale closeout lane'
_REQUIRED_SECTIONS = [
    "## Why this lane matters",
    "## Required inputs (acceleration closeout)",
    "## Command lane",
    "## Scale closeout contract",
    "## Scale quality checklist",
    "## Delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit scale-closeout --format json --strict",
    "python -m sdetkit scale-closeout --emit-pack-dir docs/artifacts/scale-closeout-pack --format json --strict",
    "python -m sdetkit scale-closeout --execute --evidence-dir docs/artifacts/scale-closeout-pack/evidence --format json --strict",
    "python scripts/check_scale_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit scale-closeout --format json --strict",
    "python -m sdetkit scale-closeout --emit-pack-dir docs/artifacts/scale-closeout-pack --format json --strict",
    "python scripts/check_scale_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    'Single owner + backup reviewer are assigned for  scale lane execution and KPI follow-up.',
    'The  scale lane references  acceleration winners and misses with deterministic growth loops.',
    'Every  section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.',
    ' closeout records scale learnings and  expansion priorities.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes scale summary, growth matrix, and rollback strategy",
    "- [ ] Every section has owner, publish window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes scale plan, growth matrix, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  scale plan draft committed',
    '- [ ]  review notes captured with owner + backup',
    '- [ ]  growth matrix exported',
    '- [ ]  KPI scorecard snapshot exported',
    '- [ ]  expansion priorities drafted from  learnings',
]

_DEFAULT_PAGE_TEMPLATE = '#  — Scale closeout lane\n\nThis lane closes with a major scale upgrade that converts acceleration evidence into deterministic improvement loops.\n\n## Why this lane matters\n\n- Converts  acceleration proof into growth-first operating motion.\n- Protects quality with owner accountability, command proof, and KPI guardrails.\n- Produces a deterministic handoff from scale outcomes into  expansion priorities.\n\n## Required inputs (acceleration closeout)\n\n- `docs/artifacts/acceleration-closeout-pack-43/acceleration-closeout-summary-43.json`\n- `docs/artifacts/acceleration-closeout-pack-43/delivery-board-43.md`\n\n## Command lane\n\n```bash\npython -m sdetkit scale-closeout --format json --strict\npython -m sdetkit scale-closeout --emit-pack-dir docs/artifacts/scale-closeout-pack --format json --strict\npython -m sdetkit scale-closeout --execute --evidence-dir docs/artifacts/scale-closeout-pack/evidence --format json --strict\npython scripts/check_scale_closeout_contract.py\n```\n\n## Scale closeout contract\n\n- Single owner + backup reviewer are assigned for  scale lane execution and KPI follow-up.\n- The  scale lane references  acceleration winners and misses with deterministic growth loops.\n- Every  section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.\n-  closeout records scale learnings and  expansion priorities.\n\n## Scale quality checklist\n\n- [ ] Includes scale summary, growth matrix, and rollback strategy\n- [ ] Every section has owner, publish window, KPI target, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI\n- [ ] Artifact pack includes scale plan, growth matrix, KPI scorecard, and execution log\n\n## Delivery board\n\n- [ ]  scale plan draft committed\n- [ ]  review notes captured with owner + backup\n- [ ]  growth matrix exported\n- [ ]  KPI scorecard snapshot exported\n- [ ]  expansion priorities drafted from  learnings\n\n## Scoring model\n\nWeighted score (0-100):\n\n- Docs contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 35 points.\n- Scale contract lock + delivery board readiness: 15 points.\n'


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _resolve_existing_path(root: Path, primary: str, legacy: str) -> Path:
    primary_path = root / primary
    if primary_path.exists():
        return primary_path
    return root / legacy


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _load_acceleration_closeout(path: Path) -> tuple[float, bool, int]:
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
    return len(items), '' in text, '' in text


def _contains_all_lines(text: str, expected: list[str]) -> list[str]:
    return [line for line in expected if line not in text]


def build_scale_closeout_summary(root: Path) -> dict[str, Any]:
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

    acceleration_closeout_summary = _resolve_existing_path(
        root, _DAY43_SUMMARY_PATH, _DAY43_LEGACY_SUMMARY_PATH
    )
    acceleration_closeout_board = _resolve_existing_path(
        root, _DAY43_BOARD_PATH, _DAY43_LEGACY_BOARD_PATH
    )
    acceleration_closeout_score, acceleration_closeout_strict, acceleration_closeout_check_count = (
        _load_acceleration_closeout(acceleration_closeout_summary)
    )
    board_count, board_has_acceleration_closeout, board_has_scale_closeout = _board_stats(
        acceleration_closeout_board
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
            "check_id": "readme_scale_closeout_link",
            "weight": 8,
            "passed": "docs/integrations-scale-closeout.md" in readme_text,
            "evidence": "docs/integrations-scale-closeout.md",
        },
        {
            "check_id": "readme_scale_closeout_command",
            "weight": 4,
            "passed": "scale-closeout" in readme_text,
            "evidence": "scale-closeout",
        },
        {
            "check_id": "docs_index_scale_closeout_links",
            "weight": 8,
            "passed": (
                "impact-44-big-upgrade-report.md" in docs_index_text
                and "integrations-scale-closeout.md" in docs_index_text
            ),
            "evidence": "impact-44-big-upgrade-report.md + integrations-scale-closeout.md",
        },
        {
            "check_id": "top10_scale_closeout_alignment",
            "weight": 5,
            "passed": ('' in top10_text and '' in top10_text),
            "evidence": "Scale closeout + expansion closeout strategy chain",
        },
        {
            "check_id": "acceleration_closeout_summary_present",
            "weight": 10,
            "passed": acceleration_closeout_summary.exists(),
            "evidence": str(acceleration_closeout_summary),
        },
        {
            "check_id": "acceleration_closeout_delivery_board_present",
            "weight": 8,
            "passed": acceleration_closeout_board.exists(),
            "evidence": str(acceleration_closeout_board),
        },
        {
            "check_id": "acceleration_closeout_quality_floor",
            "weight": 10,
            "passed": acceleration_closeout_strict and acceleration_closeout_score >= 95,
            "evidence": {
                "acceleration_closeout_score": acceleration_closeout_score,
                "strict_pass": acceleration_closeout_strict,
                "acceleration_closeout_checks": acceleration_closeout_check_count,
            },
        },
        {
            "check_id": "acceleration_closeout_board_integrity",
            "weight": 7,
            "passed": board_count >= 5
            and board_has_acceleration_closeout
            and board_has_scale_closeout,
            "evidence": {
                "board_items": board_count,
                "contains_acceleration_closeout": board_has_acceleration_closeout,
                "contains_scale_closeout": board_has_scale_closeout,
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
    if not acceleration_closeout_summary.exists() or not acceleration_closeout_board.exists():
        critical_failures.append("acceleration_closeout_handoff_inputs")
    if not acceleration_closeout_strict:
        critical_failures.append("acceleration_closeout_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if acceleration_closeout_strict:
        wins.append(
            f"43 continuity is strict-pass with activation score={acceleration_closeout_score}."
        )
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  acceleration closeout command and restore strict pass baseline before  lock.'
        )

    if board_count >= 5 and board_has_acceleration_closeout and board_has_scale_closeout:
        wins.append(
            f"43 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and /44 anchors).'
        )
        handoff_actions.append(
            'Repair  delivery board entries to include  and  anchors.'
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Scale execution contract + quality checklist is fully locked for execution.")
    else:
        misses.append("Scale contract, quality checklist, or delivery board entries are missing.")
        handoff_actions.append(
            'Complete all  scale contract lines, quality checklist entries, and delivery board tasks in docs.'
        )

    if not failed and not critical_failures:
        wins.append(
            ' scale closeout lane is fully complete and ready for  expansion lane.'
        )

    return {
        "name": "scale-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "acceleration_closeout_summary": str(acceleration_closeout_summary.relative_to(root))
            if acceleration_closeout_summary.exists()
            else str(acceleration_closeout_summary),
            "acceleration_closeout_delivery_board": str(
                acceleration_closeout_board.relative_to(root)
            )
            if acceleration_closeout_board.exists()
            else str(acceleration_closeout_board),
        },
        "checks": checks,
        "rollup": {
            "acceleration_closeout_activation_score": acceleration_closeout_score,
            "acceleration_closeout_checks": acceleration_closeout_check_count,
            "acceleration_closeout_delivery_board_items": board_count,
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
        "Scale closeout summary",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- 43 activation score: `{payload['rollup']['acceleration_closeout_activation_score']}`",
        f"- 43 checks evaluated: `{payload['rollup']['acceleration_closeout_checks']}`",
        f"- 43 delivery board checklist items: `{payload['rollup']['acceleration_closeout_delivery_board_items']}`",
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
    _write(target / "scale-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "scale-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "scale-plan.md",
        '# Scale plan\n\n- Objective: close  with measurable quality and throughput gains.\n',
    )
    _write(
        target / "scale-growth-matrix.csv",
        "stream,owner,backup,publish_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "quality-floor,qa-lead,platform-owner,2026-03-12T10:00:00Z,docs/integrations-scale-closeout.md,python -m sdetkit scale-closeout --format json --strict,failed-checks:0,baseline-drift\n",
    )
    _write(
        target / "scale-kpi-scorecard.json",
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
        target / "scale-execution-log.md",
        '# Scale execution log\n\n- [ ] 2026-03-12: Record misses, wins, and  expansion priorities.\n',
    )
    _write(
        target / "scale-delivery-board.md",
        "# Scale delivery board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "scale-validation-commands.md",
        "# Scale validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        evidence_path / "scale-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scale closeout checks")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--ensure-doc", action="store_true")
    return parser


def build_scale_closeout_summary_impl(root: Path) -> dict[str, Any]:
    'Compatibility alias for legacy -based builder name.'
    return build_scale_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.ensure_doc:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DEFAULT_PAGE_TEMPLATE)

    payload = build_scale_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/scale-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
