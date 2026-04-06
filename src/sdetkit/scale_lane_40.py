from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-scale-lane.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY39_SUMMARY_PATH = "docs/artifacts/playbook-post-pack/playbook-post-summary.json"
_DAY39_BOARD_PATH = "docs/artifacts/playbook-post-pack/delivery-board.md"
_SECTION_HEADER = '#  — Scale lane #1'
_REQUIRED_SECTIONS = [
    '## Why  matters',
    '## Required inputs ()',
    '##  command lane',
    "## Scale execution contract",
    "## Scale quality checklist",
    '##  delivery board',
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit scale-lane --format json --strict",
    "python -m sdetkit scale-lane --emit-pack-dir docs/artifacts/scale-lane-pack --format json --strict",
    "python -m sdetkit scale-lane --execute --evidence-dir docs/artifacts/scale-lane-pack/evidence --format json --strict",
    "python scripts/check_scale_lane_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit scale-lane --format json --strict",
    "python -m sdetkit scale-lane --emit-pack-dir docs/artifacts/scale-lane-pack --format json --strict",
    "python scripts/check_scale_lane_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    'Single owner + backup reviewer are assigned for  scale lane execution and metric follow-up.',
    'The  scale lane references  publication winners and explicit misses.',
    'Every  scale lane section includes docs CTA, runnable command CTA, and one KPI target.',
    ' closeout records scale learnings and  expansion priorities.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes executive summary, tactical checklist, and rollout timeline",
    "- [ ] Every section has owner, publish window, and KPI target",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, and delta for each playbook KPI",
    "- [ ] Artifact pack includes scale plan, channel matrix, scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  scale plan draft committed',
    '- [ ]  review notes captured with owner + backup',
    '- [ ]  rollout timeline exported',
    '- [ ]  KPI scorecard snapshot exported',
    '- [ ]  expansion priorities drafted from  learnings',
]

_DEFAULT_PAGE_TEMPLATE = '#  — Scale lane #1\n\n publishes scale lane #1 that converts  publication evidence into a reusable operator guide.\n\n## Why  matters\n\n- Converts  publication evidence into a reusable post + playbook operating pattern.\n- Preserves quality by enforcing owner accountability, CTA integrity, and KPI targets.\n- Creates a deterministic handoff from publication outcomes into  scale priorities.\n\n## Required inputs ()\n\n- `docs/artifacts/playbook-post-pack/playbook-post-summary.json`\n- `docs/artifacts/playbook-post-pack/delivery-board.md`\n\n##  command lane\n\n```bash\npython -m sdetkit scale-lane --format json --strict\npython -m sdetkit scale-lane --emit-pack-dir docs/artifacts/scale-lane-pack --format json --strict\npython -m sdetkit scale-lane --execute --evidence-dir docs/artifacts/scale-lane-pack/evidence --format json --strict\npython scripts/check_scale_lane_contract.py\n```\n\n## Scale execution contract\n\n- Single owner + backup reviewer are assigned for  scale lane execution and metric follow-up.\n- The  scale lane references  publication winners and explicit misses.\n- Every  scale lane section includes docs CTA, runnable command CTA, and one KPI target.\n-  closeout records scale learnings and  expansion priorities.\n\n## Scale quality checklist\n\n- [ ] Includes executive summary, tactical checklist, and rollout timeline\n- [ ] Every section has owner, publish window, and KPI target\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures baseline, current, and delta for each playbook KPI\n- [ ] Artifact pack includes scale plan, channel matrix, scorecard, and execution log\n\n##  delivery board\n\n- [ ]  scale plan draft committed\n- [ ]  review notes captured with owner + backup\n- [ ]  rollout timeline exported\n- [ ]  KPI scorecard snapshot exported\n- [ ]  expansion priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Docs contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 35 points.\n- Publication contract lock + delivery board readiness: 15 points.\n'


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


def _load_cycle39(path: Path) -> tuple[float, bool, int]:
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
    lines = [line.strip().lower() for line in text.splitlines()]
    item_count = sum(1 for line in lines if line.startswith("- [ ]"))
    has_cycle39 = any(
        any(token in line for token in ("impact 39", '', "name 39")) for line in lines
    )
    has_cycle40 = any(
        any(token in line for token in ("impact 40", '', "name 40")) for line in lines
    )
    return item_count, has_cycle39, has_cycle40


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_scale_lane_summary_impl(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
) -> dict[str, Any]:
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

    summary = root / _DAY39_SUMMARY_PATH
    board = root / _DAY39_BOARD_PATH
    score, strict, check_count = _load_cycle39(summary)
    board_count, board_has_cycle39, board_has_cycle40 = _board_stats(board)

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
            "passed": "docs/integrations-scale-lane.md" in readme_text,
            "evidence": "docs/integrations-scale-lane.md",
        },
        {
            "check_id": "readme_command_lane",
            "weight": 4,
            "passed": "scale-lane" in readme_text,
            "evidence": "scale-lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-40-big-upgrade-report.md" in docs_index_text
                and "integrations-scale-lane.md" in docs_index_text
            ),
            "evidence": "impact-40-big-upgrade-report.md + integrations-scale-lane.md",
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
            "passed": board_count >= 5 and board_has_cycle39 and board_has_cycle40,
            "evidence": {
                "board_items": board_count,
                "contains": board_has_cycle39,
                "contains": board_has_cycle40,
            },
        },
        {
            "check_id": "playbook_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "playbook_quality_checklist_locked",
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
        wins.append(f"39 continuity is strict-pass with activation score={score}.")
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  scale lane command and restore strict pass baseline before  lock.'
        )

    if board_count >= 5 and board_has_cycle39 and board_has_cycle40:
        wins.append(
            f"39 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and /40 anchors).'
        )
        handoff_actions.append(
            'Repair  delivery board entries to include  and  anchors.'
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Scale execution contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Playbook contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            'Complete all  scale contract lines, quality checklist entries, and delivery board tasks in docs.'
        )

    if not failed and not critical_failures:
        wins.append(' scale lane #1 is fully complete and ready for  expansion lane.')

    return {
        "name": "scale-lane",
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


def _to_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return (
        ' scale lane summary\n'
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        '#  scale lane summary',
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        '##  continuity',
        "",
        f"- 39 activation score: `{payload['rollup']['activation_score']}`",
        f"- 39 checks evaluated: `{payload['rollup']['checks']}`",
        f"- 39 delivery board checklist items: `{payload['rollup']['delivery_board_items']}`",
        "",
        "## Wins",
    ]
    lines.extend(f"- {item}" for item in payload["wins"])
    lines.append("\n## Misses")
    lines.extend(f"- {item}" for item in payload["misses"] or ["No misses recorded."])
    lines.append("\n## Handoff actions")
    lines.extend(
        f"- [ ] {item}" for item in payload["handoff_actions"] or ["No handoff actions required."]
    )
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _emit_pack(root: Path, payload: dict[str, Any], pack_dir: Path) -> None:
    target = (root / pack_dir).resolve() if not pack_dir.is_absolute() else pack_dir
    target.mkdir(parents=True, exist_ok=True)
    _write(target / "scale-lane-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "scale-lane-summary.md", _to_markdown(payload))
    _write(
        target / "scale-plan.md",
        '#  scale lane #1\n\n'
        "## Executive summary\n"
        '-  winners were converted into a repeatable publishing pattern.\n'
        "- Misses were mapped to actionable guardrails for next wave execution.\n\n"
        "## Tactical checklist\n"
        "- [ ] Validate owner + backup approvals\n"
        "- [ ] Publish docs + command CTA pair for each section\n"
        "- [ ] Capture KPI pulse after 24h and 72h\n",
    )
    _write(
        target / "channel-matrix.csv",
        "section,owner,backup,publish_window_utc,docs_cta,command_cta,kpi_target\n"
        "executive-summary,pm-owner,backup-pm,2026-03-06T09:00:00Z,docs/integrations-scale-lane.md,python -m sdetkit scale-lane --format json --strict,completion:+5%\n"
        "tactical-checklist,ops-owner,backup-ops,2026-03-06T12:00:00Z,docs/impact-40-big-upgrade-report.md,python scripts/check_scale_lane_contract.py,adoption:+7%\n"
        "rollout-timeline,growth-owner,backup-growth,2026-03-07T15:00:00Z,docs/top-10-github-strategy.md,python -m sdetkit scale-lane --emit-pack-dir docs/artifacts/scale-lane-pack --format json --strict,ctr:+2%\n",
    )
    _write(
        target / "scale-kpi-scorecard.json",
        json.dumps(
            {
                "generated_for": "scale-lane",
                "metrics": [
                    {
                        "name": "playbook_read_completion",
                        "baseline": 41.2,
                        "current": 44.4,
                        "delta_pct": 7.77,
                    },
                    {
                        "name": "docs_to_command_adoption",
                        "baseline": 18.6,
                        "current": 20.0,
                        "delta_pct": 7.53,
                    },
                    {
                        "name": "operator_feedback_positive",
                        "baseline": 72.0,
                        "current": 76.0,
                        "delta_pct": 5.56,
                    },
                ],
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "execution-log.md",
        '#  execution log\n\n'
        "- [ ] 2026-03-06: Publish playbook draft and collect internal review notes.\n"
        "- [ ] 2026-03-07: Execute rollout timeline and capture first KPI pulse.\n"
        '- [ ] 2026-03-08: Record misses, wins, and  scale priorities.\n',
    )
    _write(
        target / "delivery-board.md",
        '#  delivery board\n\n' + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "validation-commands.md",
        '#  validation commands\n\n```bash\n' + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
    )


def _run_execution(root: Path, evidence_dir: Path) -> None:
    target = (root / evidence_dir).resolve() if not evidence_dir.is_absolute() else evidence_dir
    target.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    for command in _EXECUTION_COMMANDS:
        argv = shlex.split(command)
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        proc = subprocess.run(argv, cwd=root, text=True, capture_output=True, check=False)
        logs.append(
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
    summary = {
        "name": "scale-lane-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=' scale lane scorer.')
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--write-defaults", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.write_defaults:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DEFAULT_PAGE_TEMPLATE)

    payload = build_scale_lane_summary_impl(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/scale-lane-pack/evidence")
        )
        _run_execution(root, ev_dir)

    if ns.format == "json":
        rendered = json.dumps(payload, indent=2) + "\n"
    elif ns.format == "markdown":
        rendered = _to_markdown(payload)
    else:
        rendered = _to_text(payload)

    if ns.output:
        _write(
            (root / ns.output).resolve() if not Path(ns.output).is_absolute() else Path(ns.output),
            rendered,
        )
    else:
        print(rendered, end="")

    if ns.strict and (
        payload["summary"]["failed_checks"] > 0 or payload["summary"]["critical_failures"]
    ):
        return 1
    return 0


def build_scale_lane_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
) -> dict[str, Any]:
    'Canonical summary builder (-based name retained as compatibility alias).'
    return build_scale_lane_summary_impl(
        root,
        readme_path=readme_path,
        docs_index_path=docs_index_path,
        docs_page_path=docs_page_path,
        top10_path=top10_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
