from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-kpi-instrumentation.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY34_SUMMARY_PATH = "docs/artifacts/demo-asset2-pack/demo-asset2-summary.json"
_DAY34_BOARD_PATH = "docs/artifacts/demo-asset2-pack/demo-asset2-delivery-board.md"
_SECTION_HEADER = '#  — KPI instrumentation closeout'
_REQUIRED_SECTIONS = [
    '## Why  matters',
    '## Required inputs ()',
    '##  command lane',
    "## KPI instrumentation contract",
    "## KPI quality checklist",
    '##  delivery board',
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit kpi-instrumentation --format json --strict",
    "python -m sdetkit kpi-instrumentation --emit-pack-dir docs/artifacts/kpi-instrumentation-pack --format json --strict",
    "python -m sdetkit kpi-instrumentation --execute --evidence-dir docs/artifacts/kpi-instrumentation-pack/evidence --format json --strict",
    "python scripts/check_kpi_instrumentation_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit kpi-instrumentation --format json --strict",
    "python -m sdetkit kpi-instrumentation --emit-pack-dir docs/artifacts/kpi-instrumentation-pack --format json --strict",
    "python scripts/check_kpi_instrumentation_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for KPI instrumentation maintenance.",
    "Metric taxonomy includes acquisition, activation, retention, and reliability slices.",
    "Every KPI has source command, cadence, owner, and threshold fields documented.",
    ' report links KPI drift to at least three concrete next-week actions.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes at least eight KPIs split across acquisition/activation/retention/reliability",
    "- [ ] Every KPI row has source command and refresh cadence",
    "- [ ] At least three threshold alerts are documented with owner + escalation action",
    "- [ ] Weekly review delta compares current week vs prior week in percentages",
    "- [ ] Artifact pack includes dashboard, alert policy, and narrative summary",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  KPI dictionary committed',
    '- [ ]  dashboard snapshot exported',
    '- [ ]  alert policy reviewed with owner + backup',
    '- [ ]  distribution message references KPI shifts',
    '- [ ]  experiment backlog seeded from KPI misses',
]

_DEFAULT_PAGE_TEMPLATE = '#  — KPI instrumentation closeout\n\n closes the instrumentation lane by converting demo activity into measurable weekly signals and next-week actions.\n\n## Why  matters\n\n- Turns demo outputs into a durable KPI operating loop.\n- Reduces attribution gaps by forcing explicit metric sources and cadence.\n- Upgrades weekly review quality from narrative-only updates to threshold-backed decisions.\n\n## Required inputs ()\n\n- `docs/artifacts/demo-asset2-pack/demo-asset2-summary.json`\n- `docs/artifacts/demo-asset2-pack/demo-asset2-delivery-board.md`\n\n##  command lane\n\n```bash\npython -m sdetkit kpi-instrumentation --format json --strict\npython -m sdetkit kpi-instrumentation --emit-pack-dir docs/artifacts/kpi-instrumentation-pack --format json --strict\npython -m sdetkit kpi-instrumentation --execute --evidence-dir docs/artifacts/kpi-instrumentation-pack/evidence --format json --strict\npython scripts/check_kpi_instrumentation_contract.py\n```\n\n## KPI instrumentation contract\n\n- Single owner + backup reviewer are assigned for KPI instrumentation maintenance.\n- Metric taxonomy includes acquisition, activation, retention, and reliability slices.\n- Every KPI has source command, cadence, owner, and threshold fields documented.\n-  report links KPI drift to at least three concrete next-week actions.\n\n## KPI quality checklist\n\n- [ ] Includes at least eight KPIs split across acquisition/activation/retention/reliability\n- [ ] Every KPI row has source command and refresh cadence\n- [ ] At least three threshold alerts are documented with owner + escalation action\n- [ ] Weekly review delta compares current week vs prior week in percentages\n- [ ] Artifact pack includes dashboard, alert policy, and narrative summary\n\n##  delivery board\n\n- [ ]  KPI dictionary committed\n- [ ]  dashboard snapshot exported\n- [ ]  alert policy reviewed with owner + backup\n- [ ]  distribution message references KPI shifts\n- [ ]  experiment backlog seeded from KPI misses\n\n## Scoring model\n\n weighted score (0-100):\n\n- Docs contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 35 points.\n- KPI contract lock + delivery board readiness: 15 points.\n'


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


def _load_cycle34(path: Path) -> tuple[float, bool, int]:
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
    has_cycle35 = any(
        any(token in line for token in ("impact 35", '', "name 35")) for line in lines
    )
    has_cycle36 = any(
        any(token in line for token in ("impact 36", '', "name 36")) for line in lines
    )
    return item_count, has_cycle35, has_cycle36


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_kpi_instrumentation_summary_impl(
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

    summary_primary = root / _DAY34_SUMMARY_PATH
    board_primary = root / _DAY34_BOARD_PATH
    summary = summary_primary
    board = board_primary
    score, strict, check_count = _load_cycle34(summary)
    board_count, board_has_cycle35, board_has_cycle36 = _board_stats(board)

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
            "check_id": "readme_kpi_instrumentation_link",
            "weight": 8,
            "passed": "docs/integrations-kpi-instrumentation.md" in readme_text,
            "evidence": "docs/integrations-kpi-instrumentation.md",
        },
        {
            "check_id": "readme_kpi_instrumentation_command",
            "weight": 4,
            "passed": "kpi-instrumentation" in readme_text,
            "evidence": "README kpi-instrumentation command lane",
        },
        {
            "check_id": "docs_index_kpi_instrumentation_links",
            "weight": 8,
            "passed": (
                "impact-35-big-upgrade-report.md" in docs_index_text
                and "integrations-kpi-instrumentation.md" in docs_index_text
            ),
            "evidence": "impact-35-big-upgrade-report.md + integrations-kpi-instrumentation.md",
        },
        {
            "check_id": "top10_kpi_instrumentation_alignment",
            "weight": 5,
            "passed": ('' in top10_text and '' in top10_text),
            "evidence": ' +  strategy chain',
        },
        {
            "check_id": "summary_present",
            "weight": 10,
            "passed": summary.exists(),
            "evidence": {"resolved": str(summary), "primary": str(summary_primary)},
        },
        {
            "check_id": "delivery_board_present",
            "weight": 8,
            "passed": board.exists(),
            "evidence": {"resolved": str(board), "primary": str(board_primary)},
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
            "passed": board_count >= 5 and board_has_cycle35 and board_has_cycle36,
            "evidence": {
                "board_items": board_count,
                "contains": board_has_cycle35,
                "contains": board_has_cycle36,
            },
        },
        {
            "check_id": "kpi_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "kpi_quality_checklist_locked",
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
        wins.append(f"34 continuity is strict-pass with activation score={score}.")
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  demo asset #2 command and restore strict pass baseline before  lock.'
        )

    if board_count >= 5 and board_has_cycle35 and board_has_cycle36:
        wins.append(
            f"34 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and /36 anchors).'
        )
        handoff_actions.append(
            'Repair  delivery board entries to include  and  anchors.'
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "KPI instrumentation contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append("KPI contract, quality checklist, or delivery board entries are missing.")
        handoff_actions.append(
            'Complete all  KPI contract lines, quality checklist entries, and delivery board tasks in docs.'
        )

    if not failed and not critical_failures:
        wins.append(
            ' KPI instrumentation closeout is fully complete and ready for  distribution execution.'
        )

    return {
        "name": "kpi-instrumentation",
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
        ' KPI instrumentation summary\n'
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        '#  KPI instrumentation summary',
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        '##  continuity',
        "",
        f"- 34 activation score: `{payload['rollup']['activation_score']}`",
        f"- 34 checks evaluated: `{payload['rollup']['checks']}`",
        f"- 34 delivery board checklist items: `{payload['rollup']['delivery_board_items']}`",
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
    _write(target / "kpi-instrumentation-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "kpi-instrumentation-summary.md", _to_markdown(payload))
    _write(
        target / "kpi-dictionary.csv",
        "metric,segment,source_command,cadence,owner,threshold,notes\n"
        "docs_unique_visitors,acquisition,python -m sdetkit report --input docs/traffic.json --format json,daily,growth-owner,>=1500,Docs traffic stability\n"
        "readme_to_command_ctr,activation,python -m sdetkit evidence-assets --format json,daily,growth-owner,>=12%,README conversion\n"
        "first_successful_run_rate,activation,python -m sdetkit doctor --json,weekly,qa-owner,>=85%,Onboarding quality\n"
        "returning_users_7d,retention,python -m sdetkit report --input analytics.json --format json,weekly,pm-owner,>=25%,Retention baseline\n"
        "discussion_reply_time_hours,reliability,python -m sdetkit ops status --format json,daily,community-owner,<=24,Community latency\n"
        "ci_flake_rate,reliability,python -m sdetkit repo audit --json,daily,eng-owner,<=3%,Stability\n"
        "release_cadence_adherence,reliability,python -m sdetkit release-readiness --format json,weekly,release-owner,>=95%,Cadence health\n"
        "external_pr_conversion,retention,python -m sdetkit contributor-funnel --format json,weekly,community-owner,>=8%,PR funnel health\n",
    )
    _write(
        target / "alert-policy.md",
        '#  alert policy\n\n'
        "- `readme_to_command_ctr < 10%` for two consecutive cycles -> owner opens remediation issue within 24h.\n"
        "- `ci_flake_rate > 3%` on daily sweep -> block release tagging until flaky tests triaged.\n"
        "- `discussion_reply_time_hours > 24` for 3+ threads -> trigger backup reviewer support shift.\n",
    )
    _write(
        target / "delivery-board.md",
        '#  delivery board\n\n' + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "kpi-instrumentation-validation-commands.md",
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
        "name": "kpi-instrumentation-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(
        target / "kpi-instrumentation-execution-summary.json", json.dumps(summary, indent=2) + "\n"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=' KPI instrumentation closeout scorer.')
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

    payload = build_kpi_instrumentation_summary_impl(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/kpi-instrumentation-pack/evidence")
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


def build_kpi_instrumentation_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
) -> dict[str, Any]:
    'Canonical summary builder (-based name retained as compatibility alias).'
    return build_kpi_instrumentation_summary_impl(
        root,
        readme_path=readme_path,
        docs_index_path=docs_index_path,
        docs_page_path=docs_page_path,
        top10_path=top10_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
