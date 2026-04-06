from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-distribution-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY35_SUMMARY_PATH = "docs/artifacts/kpi-instrumentation-pack/kpi-instrumentation-summary.json"
_DAY35_BOARD_PATH = "docs/artifacts/kpi-instrumentation-pack/delivery-board.md"
_SECTION_HEADER = '#  — Community distribution closeout'
_REQUIRED_SECTIONS = [
    '## Why  matters',
    '## Required inputs ()',
    '##  command lane',
    "## Distribution contract",
    "## Distribution quality checklist",
    '##  delivery board',
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit distribution-closeout --format json --strict",
    "python -m sdetkit distribution-closeout --emit-pack-dir docs/artifacts/distribution-closeout-pack --format json --strict",
    "python -m sdetkit distribution-closeout --execute --evidence-dir docs/artifacts/distribution-closeout-pack/evidence --format json --strict",
    "python scripts/check_distribution_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit distribution-closeout --format json --strict",
    "python -m sdetkit distribution-closeout --emit-pack-dir docs/artifacts/distribution-closeout-pack --format json --strict",
    "python scripts/check_distribution_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for distribution publishing.",
    "Primary channels include GitHub, LinkedIn, and community newsletter with explicit audience goal.",
    'Every post variant maps to one KPI from  with target delta and follow-up action.',
    ' report includes at least three  experiments seeded from distribution misses.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes at least three channel-specific message variants",
    "- [ ] Every channel variant has CTA, KPI target, and owner",
    "- [ ] Posting schedule includes exact date/time and reviewer",
    '- [ ] Engagement deltas include baseline from  metrics',
    "- [ ] Artifact pack includes launch plan, message kit, and experiment backlog",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  launch plan committed',
    '- [ ]  message kit reviewed with owner + backup',
    '- [ ]  posting windows locked',
    '- [ ]  experiment backlog seeded from channel misses',
    '- [ ]  summary owner confirmed',
]

_DEFAULT_PAGE_TEMPLATE = '#  — Community distribution closeout\n\n closes the distribution lane by converting the  KPI story into channel-ready messaging, schedule commitments, and  experiments.\n\n## Why  matters\n\n- Converts KPI insights into public distribution execution.\n- Protects consistency by defining owner, backup reviewer, and posting windows.\n- Creates a direct handoff from distribution misses into  experiment backlog.\n\n## Required inputs ()\n\n- `docs/artifacts/kpi-instrumentation-pack/kpi-instrumentation-summary.json`\n- `docs/artifacts/kpi-instrumentation-pack/delivery-board.md`\n\n##  command lane\n\n```bash\npython -m sdetkit distribution-closeout --format json --strict\npython -m sdetkit distribution-closeout --emit-pack-dir docs/artifacts/distribution-closeout-pack --format json --strict\npython -m sdetkit distribution-closeout --execute --evidence-dir docs/artifacts/distribution-closeout-pack/evidence --format json --strict\npython scripts/check_distribution_closeout_contract.py\n```\n\n## Distribution contract\n\n- Single owner + backup reviewer are assigned for distribution publishing.\n- Primary channels include GitHub, LinkedIn, and community newsletter with explicit audience goal.\n- Every post variant maps to one KPI from  with target delta and follow-up action.\n-  report includes at least three  experiments seeded from distribution misses.\n\n## Distribution quality checklist\n\n- [ ] Includes at least three channel-specific message variants\n- [ ] Every channel variant has CTA, KPI target, and owner\n- [ ] Posting schedule includes exact date/time and reviewer\n- [ ] Engagement deltas include baseline from  metrics\n- [ ] Artifact pack includes launch plan, message kit, and experiment backlog\n\n##  delivery board\n\n- [ ]  launch plan committed\n- [ ]  message kit reviewed with owner + backup\n- [ ]  posting windows locked\n- [ ]  experiment backlog seeded from channel misses\n- [ ]  summary owner confirmed\n\n## Scoring model\n\n weighted score (0-100):\n\n- Docs contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 35 points.\n- Distribution contract lock + delivery board readiness: 15 points.\n'


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


def _load_cycle35(path: Path) -> tuple[float, bool, int]:
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
    has_cycle36 = any(
        any(token in line for token in ("impact 36", '', "name 36")) for line in lines
    )
    has_cycle37 = any(
        any(token in line for token in ("impact 37", '', "name 37")) for line in lines
    )
    return item_count, has_cycle36, has_cycle37


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_distribution_closeout_summary_impl(
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

    summary = root / _DAY35_SUMMARY_PATH
    board = root / _DAY35_BOARD_PATH
    score, strict, check_count = _load_cycle35(summary)
    board_count, board_has_cycle36, board_has_cycle37 = _board_stats(board)

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
            "passed": "docs/integrations-distribution-closeout.md" in readme_text,
            "evidence": "docs/integrations-distribution-closeout.md",
        },
        {
            "check_id": "readme_command_lane",
            "weight": 4,
            "passed": "distribution-closeout" in readme_text,
            "evidence": "distribution-closeout",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-36-big-upgrade-report.md" in docs_index_text
                and "integrations-distribution-closeout.md" in docs_index_text
            ),
            "evidence": "impact-36-big-upgrade-report.md + integrations-distribution-closeout.md",
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
            "passed": board_count >= 5 and board_has_cycle36 and board_has_cycle37,
            "evidence": {
                "board_items": board_count,
                "contains": board_has_cycle36,
                "contains": board_has_cycle37,
            },
        },
        {
            "check_id": "distribution_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "distribution_quality_checklist_locked",
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
        wins.append(f"35 continuity is strict-pass with activation score={score}.")
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  KPI instrumentation command and restore strict pass baseline before  lock.'
        )

    if board_count >= 5 and board_has_cycle36 and board_has_cycle37:
        wins.append(
            f"35 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and /37 anchors).'
        )
        handoff_actions.append(
            'Repair  delivery board entries to include  and  anchors.'
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Distribution contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Distribution contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            'Complete all  distribution contract lines, quality checklist entries, and delivery board tasks in docs.'
        )

    if not failed and not critical_failures:
        wins.append(
            ' community distribution closeout is fully complete and ready for  experiment execution.'
        )

    return {
        "name": "distribution-closeout",
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
        ' community distribution summary\n'
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        '#  community distribution summary',
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        '##  continuity',
        "",
        f"- 35 activation score: `{payload['rollup']['activation_score']}`",
        f"- 35 checks evaluated: `{payload['rollup']['checks']}`",
        f"- 35 delivery board checklist items: `{payload['rollup']['delivery_board_items']}`",
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
    _write(target / "distribution-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "distribution-closeout-summary.md", _to_markdown(payload))
    _write(
        target / "distribution-message-kit.md",
        '#  distribution message kit\n\n'
        "## GitHub discussion post\n"
        '- Hook:  KPI loop is closed and measurable.\n'
        "- CTA: Try `python -m sdetkit distribution-closeout --format json --strict` and share score deltas.\n"
        "- KPI target: `readme_to_command_ctr +2%`.\n\n"
        "## LinkedIn post\n"
        "- Hook: We turned SDET growth metrics into an execution lane in 24 hours.\n"
        "- CTA: Comment your distribution bottleneck + we'll publish a playbook update.\n"
        "- KPI target: `docs_unique_visitors +10% week-over-week`.\n\n"
        "## Newsletter block\n"
        "- Hook: Security-gate demo now has full distribution + experiment handoff.\n"
        "- CTA: Forward to one maintainer who needs a repeatable contributor funnel loop.\n"
        "- KPI target: `external_pr_conversion +1.5%`.\n",
    )
    _write(
        target / "launch-plan.csv",
        "channel,publish_at_utc,owner,backup,cta,kpi_target\n"
        "github_discussion,2026-02-26T15:00:00Z,community-owner,backup-reviewer,Run cycle36 command and share score,readme_to_command_ctr:+2%\n"
        "linkedin,2026-02-26T17:30:00Z,growth-owner,backup-reviewer,Comment your bottleneck,docs_unique_visitors:+10%\n"
        "newsletter,2026-02-27T09:00:00Z,pm-owner,backup-reviewer,Forward to one maintainer,external_pr_conversion:+1.5%\n",
    )
    _write(
        target / "experiment-backlog.md",
        '#  experiment backlog seeded on \n\n'
        "- [ ] Test CTA variant: command-first vs narrative-first headline on GitHub discussion.\n"
        "- [ ] Compare morning vs afternoon LinkedIn posting window for CTR lift.\n"
        "- [ ] Add short GIF teaser to newsletter block and track reply rate delta.\n",
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
        "name": "distribution-closeout-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=' community distribution closeout scorer.')
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

    payload = build_distribution_closeout_summary_impl(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/distribution-closeout-pack/evidence")
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


def build_distribution_closeout_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
) -> dict[str, Any]:
    'Canonical summary builder (-based name retained as compatibility alias).'
    return build_distribution_closeout_summary_impl(
        root,
        readme_path=readme_path,
        docs_index_path=docs_index_path,
        docs_page_path=docs_page_path,
        top10_path=top10_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
