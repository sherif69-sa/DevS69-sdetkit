from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day39-playbook-post.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY38_SUMMARY_PATH = (
    "docs/artifacts/day38-distribution-batch-pack/day38-distribution-batch-summary.json"
)
_DAY38_BOARD_PATH = "docs/artifacts/day38-distribution-batch-pack/day38-delivery-board.md"
_SECTION_HEADER = "# Day 39 — Playbook post #1"
_REQUIRED_SECTIONS = [
    "## Why Day 39 matters",
    "## Required inputs (Day 38)",
    "## Day 39 command lane",
    "## Playbook publication contract",
    "## Playbook quality checklist",
    "## Day 39 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day39-playbook-post --format json --strict",
    "python -m sdetkit day39-playbook-post --emit-pack-dir docs/artifacts/day39-playbook-post-pack --format json --strict",
    "python -m sdetkit day39-playbook-post --execute --evidence-dir docs/artifacts/day39-playbook-post-pack/evidence --format json --strict",
    "python scripts/check_day39_playbook_post_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day39-playbook-post --format json --strict",
    "python -m sdetkit day39-playbook-post --emit-pack-dir docs/artifacts/day39-playbook-post-pack --format json --strict",
    "python scripts/check_day39_playbook_post_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 39 playbook publication and metric follow-up.",
    "The Day 39 playbook post references Day 38 distribution winners and explicit misses.",
    "Every Day 39 playbook section includes docs CTA, runnable command CTA, and one KPI target.",
    "Day 39 closeout records publication learnings and Day 40 scale priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes executive summary, tactical checklist, and rollout timeline",
    "- [ ] Every section has owner, publish window, and KPI target",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, and delta for each playbook KPI",
    "- [ ] Artifact pack includes playbook draft, rollout plan, scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 39 playbook draft committed",
    "- [ ] Day 39 review notes captured with owner + backup",
    "- [ ] Day 39 rollout timeline exported",
    "- [ ] Day 39 KPI scorecard snapshot exported",
    "- [ ] Day 40 scale priorities drafted from Day 39 learnings",
]

_DAY39_DEFAULT_PAGE = """# Day 39 — Playbook post #1

Day 39 publishes playbook post #1 that converts Day 38 distribution evidence into a reusable operator guide.

## Why Day 39 matters

- Converts Day 38 distribution evidence into a reusable post + playbook operating pattern.
- Preserves quality by enforcing owner accountability, CTA integrity, and KPI targets.
- Creates a deterministic handoff from publication outcomes into Day 40 scale priorities.

## Required inputs (Day 38)

- `docs/artifacts/day38-distribution-batch-pack/day38-distribution-batch-summary.json`
- `docs/artifacts/day38-distribution-batch-pack/day38-delivery-board.md`

## Day 39 command lane

```bash
python -m sdetkit day39-playbook-post --format json --strict
python -m sdetkit day39-playbook-post --emit-pack-dir docs/artifacts/day39-playbook-post-pack --format json --strict
python -m sdetkit day39-playbook-post --execute --evidence-dir docs/artifacts/day39-playbook-post-pack/evidence --format json --strict
python scripts/check_day39_playbook_post_contract.py
```

## Playbook publication contract

- Single owner + backup reviewer are assigned for Day 39 playbook publication and metric follow-up.
- The Day 39 playbook post references Day 38 distribution winners and explicit misses.
- Every Day 39 playbook section includes docs CTA, runnable command CTA, and one KPI target.
- Day 39 closeout records publication learnings and Day 40 scale priorities.

## Playbook quality checklist

- [ ] Includes executive summary, tactical checklist, and rollout timeline
- [ ] Every section has owner, publish window, and KPI target
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, and delta for each playbook KPI
- [ ] Artifact pack includes playbook draft, rollout plan, scorecard, and execution log

## Day 39 delivery board

- [ ] Day 39 playbook draft committed
- [ ] Day 39 review notes captured with owner + backup
- [ ] Day 39 rollout timeline exported
- [ ] Day 39 KPI scorecard snapshot exported
- [ ] Day 40 scale priorities drafted from Day 39 learnings

## Scoring model

Day 39 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 38 continuity and strict baseline carryover: 35 points.
- Publication contract lock + delivery board readiness: 15 points.
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


def _load_day38(path: Path) -> tuple[float, bool, int]:
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
    has_day38 = any("day 38" in line for line in lines)
    has_day39 = any("day 39" in line for line in lines)
    return item_count, has_day38, has_day39


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_day39_playbook_post_summary(
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

    day38_summary = root / _DAY38_SUMMARY_PATH
    day38_board = root / _DAY38_BOARD_PATH
    day38_score, day38_strict, day38_check_count = _load_day38(day38_summary)
    board_count, board_has_day38, board_has_day39 = _board_stats(day38_board)

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
            "check_id": "readme_day39_link",
            "weight": 8,
            "passed": "docs/integrations-day39-playbook-post.md" in readme_text,
            "evidence": "docs/integrations-day39-playbook-post.md",
        },
        {
            "check_id": "readme_day39_command",
            "weight": 4,
            "passed": "day39-playbook-post" in readme_text,
            "evidence": "day39-playbook-post",
        },
        {
            "check_id": "docs_index_day39_links",
            "weight": 8,
            "passed": (
                "day-39-big-upgrade-report.md" in docs_index_text
                and "integrations-day39-playbook-post.md" in docs_index_text
            ),
            "evidence": "day-39-big-upgrade-report.md + integrations-day39-playbook-post.md",
        },
        {
            "check_id": "top10_day39_alignment",
            "weight": 5,
            "passed": ("Day 39" in top10_text and "Day 40" in top10_text),
            "evidence": "Day 39 + Day 40 strategy chain",
        },
        {
            "check_id": "day38_summary_present",
            "weight": 10,
            "passed": day38_summary.exists(),
            "evidence": str(day38_summary),
        },
        {
            "check_id": "day38_delivery_board_present",
            "weight": 8,
            "passed": day38_board.exists(),
            "evidence": str(day38_board),
        },
        {
            "check_id": "day38_quality_floor",
            "weight": 10,
            "passed": day38_strict and day38_score >= 95,
            "evidence": {
                "day38_score": day38_score,
                "strict_pass": day38_strict,
                "day38_checks": day38_check_count,
            },
        },
        {
            "check_id": "day38_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day38 and board_has_day39,
            "evidence": {
                "board_items": board_count,
                "contains_day38": board_has_day38,
                "contains_day39": board_has_day39,
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
    if not day38_summary.exists() or not day38_board.exists():
        critical_failures.append("day38_handoff_inputs")
    if not day38_strict:
        critical_failures.append("day38_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day38_strict:
        wins.append(f"Day 38 continuity is strict-pass with activation score={day38_score}.")
    else:
        misses.append("Day 38 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 38 distribution batch command and restore strict pass baseline before Day 39 lock."
        )

    if board_count >= 5 and board_has_day38 and board_has_day39:
        wins.append(
            f"Day 38 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 38 delivery board integrity is incomplete (needs >=5 items and Day 38/39 anchors)."
        )
        handoff_actions.append(
            "Repair Day 38 delivery board entries to include Day 38 and Day 39 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Playbook publication contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Playbook contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 39 playbook contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append("Day 39 playbook post #1 is fully complete and ready for Day 40 scale lane.")

    return {
        "name": "day39-playbook-post",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day38_summary": str(day38_summary.relative_to(root))
            if day38_summary.exists()
            else str(day38_summary),
            "day38_delivery_board": str(day38_board.relative_to(root))
            if day38_board.exists()
            else str(day38_board),
        },
        "checks": checks,
        "rollup": {
            "day38_activation_score": day38_score,
            "day38_checks": day38_check_count,
            "day38_delivery_board_items": board_count,
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
        "Day 39 playbook post summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Day 39 playbook post summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## Day 38 continuity",
        "",
        f"- Day 38 activation score: `{payload['rollup']['day38_activation_score']}`",
        f"- Day 38 checks evaluated: `{payload['rollup']['day38_checks']}`",
        f"- Day 38 delivery board checklist items: `{payload['rollup']['day38_delivery_board_items']}`",
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
    _write(target / "day39-playbook-post-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day39-playbook-post-summary.md", _to_markdown(payload))
    _write(
        target / "day39-playbook-draft.md",
        "# Day 39 playbook post #1\n\n"
        "## Executive summary\n"
        "- Day 38 winners were converted into a repeatable publishing pattern.\n"
        "- Misses were mapped to actionable guardrails for next wave execution.\n\n"
        "## Tactical checklist\n"
        "- [ ] Validate owner + backup approvals\n"
        "- [ ] Publish docs + command CTA pair for each section\n"
        "- [ ] Capture KPI pulse after 24h and 72h\n",
    )
    _write(
        target / "day39-rollout-plan.csv",
        "section,owner,backup,publish_window_utc,docs_cta,command_cta,kpi_target\n"
        "executive-summary,pm-owner,backup-pm,2026-03-06T09:00:00Z,docs/integrations-day39-playbook-post.md,python -m sdetkit day39-playbook-post --format json --strict,completion:+5%\n"
        "tactical-checklist,ops-owner,backup-ops,2026-03-06T12:00:00Z,docs/day-39-big-upgrade-report.md,python scripts/check_day39_playbook_post_contract.py,adoption:+7%\n"
        "rollout-timeline,growth-owner,backup-growth,2026-03-07T15:00:00Z,docs/top-10-github-strategy.md,python -m sdetkit day39-playbook-post --emit-pack-dir docs/artifacts/day39-playbook-post-pack --format json --strict,ctr:+2%\n",
    )
    _write(
        target / "day39-kpi-scorecard.json",
        json.dumps(
            {
                "generated_for": "day39-playbook-post",
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
        target / "day39-execution-log.md",
        "# Day 39 execution log\n\n"
        "- [ ] 2026-03-06: Publish playbook draft and collect internal review notes.\n"
        "- [ ] 2026-03-07: Execute rollout timeline and capture first KPI pulse.\n"
        "- [ ] 2026-03-08: Record misses, wins, and Day 40 scale priorities.\n",
    )
    _write(
        target / "day39-delivery-board.md",
        "# Day 39 delivery board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day39-validation-commands.md",
        "# Day 39 validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
    )


def _run_execution(root: Path, evidence_dir: Path) -> None:
    target = (root / evidence_dir).resolve() if not evidence_dir.is_absolute() else evidence_dir
    target.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    for command in _EXECUTION_COMMANDS:
        proc = subprocess.run(
            shlex.split(command), cwd=root, text=True, capture_output=True, check=False
        )
        logs.append(
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
    summary = {
        "name": "day39-playbook-post-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "day39-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 39 playbook post scorer.")
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
            _write(page, _DAY39_DEFAULT_PAGE)

    payload = build_day39_playbook_post_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day39-playbook-post-pack/evidence")
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


if __name__ == "__main__":
    raise SystemExit(main())
