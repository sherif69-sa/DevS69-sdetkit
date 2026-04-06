from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-phase2-kickoff.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_CANONICAL_LANE_NAME = "phase2-kickoff"
_LEGACY_LANE_NAME = "legacy-phase2-kickoff"
_DAY30_SUMMARY_PATH = "docs/artifacts/phase1-wrap-pack/phase1-wrap-summary.json"
_DAY30_BACKLOG_PATH = "docs/artifacts/phase1-wrap-pack/phase1-wrap-phase2-backlog.md"
_SECTION_HEADER = '#  — Phase-2 kickoff baseline'
_REQUIRED_SECTIONS = [
    '## Why  matters',
    '## Required inputs ()',
    '##  command lane',
    "## Baseline + weekly targets",
    '##  delivery board',
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit phase2-kickoff --format json --strict",
    "python -m sdetkit phase2-kickoff --emit-pack-dir docs/artifacts/phase2-kickoff-pack --format json --strict",
    "python -m sdetkit phase2-kickoff --execute --evidence-dir docs/artifacts/phase2-kickoff-pack/evidence --format json --strict",
    "python scripts/check_phase2_kickoff_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit phase2-kickoff --format json --strict",
    "python -m sdetkit phase2-kickoff --emit-pack-dir docs/artifacts/phase2-kickoff-pack --format json --strict",
    "python scripts/check_phase2_kickoff_contract.py --skip-evidence",
]
_REQUIRED_WEEKLY_TARGET_LINES = [
    "Week-1 Phase-2 target: maintain activation score >= 95 and preserve strict pass.",
    "Week-1 growth target: publish 3 external-facing assets and 1 KPI checkpoint.",
    "Week-1 quality gate: every shipped action includes command evidence and a summary artifact.",
    "Week-1 decision gate: if any target misses, publish corrective actions in the next weekly review.",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  baseline metrics snapshot emitted',
    '- [ ]  release cadence checklist drafted',
    '- [ ]  demo asset plan (doctor) assigned',
    '- [ ]  demo asset plan (repo audit) assigned',
    '- [ ]  weekly review preparation checklist ready',
]

_DEFAULT_PAGE_TEMPLATE = '#  — Phase-2 kickoff baseline\n\n starts Phase-2 with a measurable baseline carried over from  and a fixed weekly growth target set.\n\n## Why  matters\n\n- Converts  handoff into a measurable execution contract.\n- Locks objective targets so weekly reviews can score progress without ambiguity.\n- Forces evidence-backed growth planning before feature/distribution expansion.\n\n## Required inputs ()\n\n- `docs/artifacts/phase1-wrap-pack/phase1-wrap-summary.json` (primary)\n- `docs/artifacts/phase1-wrap-pack/phase1-wrap-phase2-backlog.md` (primary)\n\n##  command lane\n\n```bash\npython -m sdetkit phase2-kickoff --format json --strict\npython -m sdetkit phase2-kickoff --emit-pack-dir docs/artifacts/phase2-kickoff-pack --format json --strict\npython -m sdetkit phase2-kickoff --execute --evidence-dir docs/artifacts/phase2-kickoff-pack/evidence --format json --strict\npython scripts/check_phase2_kickoff_contract.py\n```\n\n## Baseline + weekly targets\n\n- Baseline source:  activation score and closeout rollup.\n- Week-1 Phase-2 target: maintain activation score >= 95 and preserve strict pass.\n- Week-1 growth target: publish 3 external-facing assets and 1 KPI checkpoint.\n- Week-1 quality gate: every shipped action includes command evidence and a summary artifact.\n- Week-1 decision gate: if any target misses, publish corrective actions in the next weekly review.\n\n##  delivery board\n\n- [ ]  baseline metrics snapshot emitted\n- [ ]  release cadence checklist drafted\n- [ ]  demo asset plan (doctor) assigned\n- [ ]  demo asset plan (repo audit) assigned\n- [ ]  weekly review preparation checklist ready\n\n## Scoring model\n\n weighted score (0-100):\n\n- Docs contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and quality baseline: 35 points.\n- Week-1 target and delivery board lock: 15 points.\n'


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


def _load_cycle30(path: Path) -> tuple[float, bool, float]:
    data = _load_json(path)
    if data is None:
        return 0.0, False, 0.0
    summary = data.get("summary")
    rollup = data.get("rollup")
    score = summary.get("activation_score") if isinstance(summary, dict) else None
    strict_pass = summary.get("strict_pass") if isinstance(summary, dict) else False
    avg = rollup.get("average_activation_score") if isinstance(rollup, dict) else None
    resolved_score = float(score) if isinstance(score, (int, float)) else 0.0
    resolved_avg = float(avg) if isinstance(avg, (int, float)) else 0.0
    return resolved_score, bool(strict_pass), resolved_avg


def _backlog_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    lines = [line.strip().lower() for line in text.splitlines()]
    item_count = sum(1 for line in lines if line.startswith("- [ ]"))
    has_cycle31 = any(
        any(token in line for token in ("impact 31", '', "name 31")) for line in lines
    )
    has_cycle32 = any(
        any(token in line for token in ("impact 32", '', "name 32")) for line in lines
    )
    return item_count, has_cycle31, has_cycle32


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_phase2_kickoff_summary_impl(
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
    missing_targets = _contains_all_lines(
        page_text, [f"- {line}" for line in _REQUIRED_WEEKLY_TARGET_LINES]
    )
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    summary_primary = root / _DAY30_SUMMARY_PATH
    backlog_primary = root / _DAY30_BACKLOG_PATH
    summary = summary_primary
    backlog = backlog_primary
    score, strict, avg = _load_cycle30(summary)
    backlog_count, backlog_has_cycle31, backlog_has_cycle32 = _backlog_stats(backlog)

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
            "passed": "docs/integrations-phase2-kickoff.md" in readme_text,
            "evidence": "docs/integrations-phase2-kickoff.md",
        },
        {
            "check_id": "readme_command_lane",
            "weight": 4,
            "passed": ("phase2-kickoff" in readme_text) or ("cycle31-phase2-kickoff" in readme_text),
            "evidence": "phase2-kickoff (legacy: legacy-phase2-kickoff; historical: cycle31-phase2-kickoff)",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-31-ultra-upgrade-report.md" in docs_index_text
                and "integrations-phase2-kickoff.md" in docs_index_text
            ),
            "evidence": "impact-31-ultra-upgrade-report.md + integrations-phase2-kickoff.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": (
                ' — Phase-2 kickoff' in top10_text
                and ' — Release cadence setup' in top10_text
            ),
            "evidence": ' +  strategy chain',
        },
        {
            "check_id": "summary_present",
            "weight": 10,
            "passed": summary.exists(),
            "evidence": {
                "resolved": str(summary),
                "primary": str(summary_primary),
            },
        },
        {
            "check_id": "backlog_present",
            "weight": 8,
            "passed": backlog.exists(),
            "evidence": {
                "resolved": str(backlog),
                "primary": str(backlog_primary),
            },
        },
        {
            "check_id": "quality_floor",
            "weight": 10,
            "passed": strict and score >= 95 and avg >= 95,
            "evidence": {
                "score": score,
                "average": avg,
                "strict_pass": strict,
            },
        },
        {
            "check_id": "phase2_backlog_integrity",
            "weight": 7,
            "passed": backlog_count >= 8 and backlog_has_cycle31 and backlog_has_cycle32,
            "evidence": {
                "backlog_items": backlog_count,
                "contains": backlog_has_cycle31,
                "contains": backlog_has_cycle32,
            },
        },
        {
            "check_id": "weekly_target_contract",
            "weight": 5,
            "passed": not missing_targets,
            "evidence": {"missing_target_lines": missing_targets},
        },
        {
            "check_id": "delivery_board_locked",
            "weight": 5,
            "passed": not missing_board_items,
            "evidence": {"missing_board_items": missing_board_items},
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    critical_failures: list[str] = []
    if not summary.exists() or not backlog.exists():
        critical_failures.append("handoff_inputs")
    if not strict:
        critical_failures.append("strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if strict:
        wins.append(
            f"30 continuity is strict-pass with score={score} and avg={avg}."
        )
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  wrap command and restore strict pass baseline before Phase-2 expansion.'
        )

    if backlog_count >= 8 and backlog_has_cycle31 and backlog_has_cycle32:
        wins.append(f"Phase-2 backlog integrity validated with {backlog_count} checklist items.")
    else:
        misses.append(
            'Phase-2 backlog integrity is incomplete (needs >=8 items and /32 anchors).'
        )
        handoff_actions.append(
            'Repair  backlog to include at least 8 items with explicit  and  lines.'
        )

    if not missing_targets and not missing_board_items:
        wins.append('Week-1 targets and  delivery board are fully locked.')
    else:
        misses.append("Week-1 target contract or delivery board entries are missing.")
        handoff_actions.append(
            'Complete all  target lines and delivery board checklist entries in integration docs.'
        )

    if not failed and not critical_failures:
        wins.append(
            ' kickoff is fully closed and ready for  release-cadence execution.'
        )

    return {
        "name": _CANONICAL_LANE_NAME,
        "legacy_name": _LEGACY_LANE_NAME,
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "summary": str(summary.relative_to(root))
            if summary.exists()
            else str(summary),
            "backlog": str(backlog.relative_to(root))
            if backlog.exists()
            else str(backlog),
        },
        "checks": checks,
        "rollup": {
            "activation_score": score,
            "average_activation_score": avg,
            "backlog_items": backlog_count,
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
        ' phase-2 kickoff summary\n'
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        '#  phase-2 kickoff summary',
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        '##  continuity',
        "",
        f"- 30 activation score: `{payload['rollup']['activation_score']}`",
        f"- 30 average activation score: `{payload['rollup']['average_activation_score']}`",
        f"- 30 backlog checklist items: `{payload['rollup']['backlog_items']}`",
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
    summary_json = json.dumps(payload, indent=2) + "\n"
    _write(target / "phase2-kickoff-summary.json", summary_json)
    summary_md = _to_markdown(payload)
    _write(target / "phase2-kickoff-summary.md", summary_md)
    baseline_json = (
        json.dumps(
            {
                "impact": 31,
                "baseline": {
                    "activation_score": payload["rollup"]["activation_score"],
                    "average_activation_score": payload["rollup"][
                        "average_activation_score"
                    ],
                    "backlog_items": payload["rollup"]["backlog_items"],
                },
                "week1_targets": {
                    "activation_score_floor": 95,
                    "external_assets": 3,
                    "kpi_checkpoints": 1,
                },
            },
            indent=2,
        )
        + "\n"
    )
    _write(
        target / "phase2-kickoff-baseline-snapshot.json",
        baseline_json,
    )
    board_md = '#  delivery board\n\n' + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n"
    _write(
        target / "phase2-kickoff-delivery-board.md",
        board_md,
    )
    validation_md = (
        '#  validation commands\n\n```bash\n' + "\n".join(_REQUIRED_COMMANDS) + "\n```\n"
    )
    _write(
        target / "phase2-kickoff-validation-commands.md",
        validation_md,
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
        "name": "phase2-kickoff-execution",
        "legacy_name": "legacy-phase2-kickoff-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    execution_json = json.dumps(summary, indent=2) + "\n"
    _write(target / "phase2-kickoff-execution-summary.json", execution_json)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=' phase-2 kickoff baseline scorer.')
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

    payload = build_phase2_kickoff_summary_impl(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/phase2-kickoff-pack/evidence")
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


def build_phase2_kickoff_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
) -> dict[str, Any]:
    'Canonical summary builder (-based name retained as compatibility alias).'
    return build_phase2_kickoff_summary_impl(
        root,
        readme_path=readme_path,
        docs_index_path=docs_index_path,
        docs_page_path=docs_page_path,
        top10_path=top10_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
