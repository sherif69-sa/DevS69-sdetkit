from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day38-distribution-batch.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY37_SUMMARY_PATH = "docs/artifacts/day37-experiment-lane-pack/day37-experiment-lane-summary.json"
_DAY37_BOARD_PATH = "docs/artifacts/day37-experiment-lane-pack/day37-delivery-board.md"
_SECTION_HEADER = "# Day 38 — Distribution batch #1"
_REQUIRED_SECTIONS = [
    "## Why Day 38 matters",
    "## Required inputs (Day 37)",
    "## Day 38 command lane",
    "## Distribution contract",
    "## Distribution quality checklist",
    "## Day 38 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day38-distribution-batch --format json --strict",
    "python -m sdetkit day38-distribution-batch --emit-pack-dir docs/artifacts/day38-distribution-batch-pack --format json --strict",
    "python -m sdetkit day38-distribution-batch --execute --evidence-dir docs/artifacts/day38-distribution-batch-pack/evidence --format json --strict",
    "python scripts/check_day38_distribution_batch_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day38-distribution-batch --format json --strict",
    "python -m sdetkit day38-distribution-batch --emit-pack-dir docs/artifacts/day38-distribution-batch-pack --format json --strict",
    "python scripts/check_day38_distribution_batch_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 38 posting execution and outcome logging.",
    "At least three coordinated channel posts are linked to Day 37 winners and mapped to audience segments.",
    "Every Day 38 post includes docs CTA, command CTA, and one measurable KPI target.",
    "Day 38 closeout records winners, misses, and Day 39 playbook-post priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes at least three coordinated posts across distinct channels",
    "- [ ] Every post has owner, scheduled window, and KPI target",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, and delta for each channel KPI",
    "- [ ] Artifact pack includes channel plan, post copy, scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 38 channel plan committed",
    "- [ ] Day 38 post copy reviewed with owner + backup",
    "- [ ] Day 38 scheduling matrix exported",
    "- [ ] Day 38 KPI scorecard snapshot exported",
    "- [ ] Day 39 playbook post priorities drafted from Day 38 outcomes",
]

_DAY38_DEFAULT_PAGE = """# Day 38 — Distribution batch #1

Day 38 publishes a coordinated distribution batch that operationalizes Day 37 experiment winners into high-signal channel execution.

## Why Day 38 matters

- Converts Day 37 learning into external distribution outcomes across multiple channels.
- Preserves quality by enforcing owner accountability, CTA integrity, and KPI targets.
- Creates a deterministic handoff from distribution outcomes into Day 39 playbook content priorities.

## Required inputs (Day 37)

- `docs/artifacts/day37-experiment-lane-pack/day37-experiment-lane-summary.json`
- `docs/artifacts/day37-experiment-lane-pack/day37-delivery-board.md`

## Day 38 command lane

```bash
python -m sdetkit day38-distribution-batch --format json --strict
python -m sdetkit day38-distribution-batch --emit-pack-dir docs/artifacts/day38-distribution-batch-pack --format json --strict
python -m sdetkit day38-distribution-batch --execute --evidence-dir docs/artifacts/day38-distribution-batch-pack/evidence --format json --strict
python scripts/check_day38_distribution_batch_contract.py
```

## Distribution contract

- Single owner + backup reviewer are assigned for Day 38 posting execution and outcome logging.
- At least three coordinated channel posts are linked to Day 37 winners and mapped to audience segments.
- Every Day 38 post includes docs CTA, command CTA, and one measurable KPI target.
- Day 38 closeout records winners, misses, and Day 39 playbook-post priorities.

## Distribution quality checklist

- [ ] Includes at least three coordinated posts across distinct channels
- [ ] Every post has owner, scheduled window, and KPI target
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, and delta for each channel KPI
- [ ] Artifact pack includes channel plan, post copy, scorecard, and execution log

## Day 38 delivery board

- [ ] Day 38 channel plan committed
- [ ] Day 38 post copy reviewed with owner + backup
- [ ] Day 38 scheduling matrix exported
- [ ] Day 38 KPI scorecard snapshot exported
- [ ] Day 39 playbook post priorities drafted from Day 38 outcomes

## Scoring model

Day 38 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 37 continuity and strict baseline carryover: 35 points.
- Distribution contract lock + delivery board readiness: 15 points.
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


def _load_day37(path: Path) -> tuple[float, bool, int]:
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
    has_day37 = any("day 37" in line for line in lines)
    has_day38 = any("day 38" in line for line in lines)
    return item_count, has_day37, has_day38


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_day38_distribution_batch_summary(
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

    day37_summary = root / _DAY37_SUMMARY_PATH
    day37_board = root / _DAY37_BOARD_PATH
    day37_score, day37_strict, day37_check_count = _load_day37(day37_summary)
    board_count, board_has_day37, board_has_day38 = _board_stats(day37_board)

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
            "check_id": "readme_day38_link",
            "weight": 8,
            "passed": "docs/integrations-day38-distribution-batch.md" in readme_text,
            "evidence": "docs/integrations-day38-distribution-batch.md",
        },
        {
            "check_id": "readme_day38_command",
            "weight": 4,
            "passed": "day38-distribution-batch" in readme_text,
            "evidence": "day38-distribution-batch",
        },
        {
            "check_id": "docs_index_day38_links",
            "weight": 8,
            "passed": (
                "day-38-big-upgrade-report.md" in docs_index_text
                and "integrations-day38-distribution-batch.md" in docs_index_text
            ),
            "evidence": "day-38-big-upgrade-report.md + integrations-day38-distribution-batch.md",
        },
        {
            "check_id": "top10_day38_alignment",
            "weight": 5,
            "passed": ("Day 38" in top10_text and "Day 39" in top10_text),
            "evidence": "Day 38 + Day 39 strategy chain",
        },
        {
            "check_id": "day37_summary_present",
            "weight": 10,
            "passed": day37_summary.exists(),
            "evidence": str(day37_summary),
        },
        {
            "check_id": "day37_delivery_board_present",
            "weight": 8,
            "passed": day37_board.exists(),
            "evidence": str(day37_board),
        },
        {
            "check_id": "day37_quality_floor",
            "weight": 10,
            "passed": day37_strict and day37_score >= 95,
            "evidence": {
                "day37_score": day37_score,
                "strict_pass": day37_strict,
                "day37_checks": day37_check_count,
            },
        },
        {
            "check_id": "day37_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day37 and board_has_day38,
            "evidence": {
                "board_items": board_count,
                "contains_day37": board_has_day37,
                "contains_day38": board_has_day38,
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
    if not day37_summary.exists() or not day37_board.exists():
        critical_failures.append("day37_handoff_inputs")
    if not day37_strict:
        critical_failures.append("day37_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day37_strict:
        wins.append(f"Day 37 continuity is strict-pass with activation score={day37_score}.")
    else:
        misses.append("Day 37 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 37 experiment lane command and restore strict pass baseline before Day 38 lock."
        )

    if board_count >= 5 and board_has_day37 and board_has_day38:
        wins.append(
            f"Day 37 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 37 delivery board integrity is incomplete (needs >=5 items and Day 37/38 anchors)."
        )
        handoff_actions.append(
            "Repair Day 37 delivery board entries to include Day 37 and Day 38 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Distribution contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Distribution contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 38 distribution contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 38 distribution batch #1 is fully complete and ready for Day 39 playbook post #1."
        )

    return {
        "name": "day38-distribution-batch",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day37_summary": str(day37_summary.relative_to(root))
            if day37_summary.exists()
            else str(day37_summary),
            "day37_delivery_board": str(day37_board.relative_to(root))
            if day37_board.exists()
            else str(day37_board),
        },
        "checks": checks,
        "rollup": {
            "day37_activation_score": day37_score,
            "day37_checks": day37_check_count,
            "day37_delivery_board_items": board_count,
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
        "Day 38 distribution batch summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Day 38 distribution batch summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## Day 37 continuity",
        "",
        f"- Day 37 activation score: `{payload['rollup']['day37_activation_score']}`",
        f"- Day 37 checks evaluated: `{payload['rollup']['day37_checks']}`",
        f"- Day 37 delivery board checklist items: `{payload['rollup']['day37_delivery_board_items']}`",
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
    _write(target / "day38-distribution-batch-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day38-distribution-batch-summary.md", _to_markdown(payload))
    _write(
        target / "day38-channel-plan.csv",
        "channel,post_id,experiment_winner,docs_cta,command_cta,owner,window_utc,kpi_target\n"
        "github,gh-01,exp-01,README:docs/integrations-day37-experiment-lane.md,python -m sdetkit day37-experiment-lane --format json,community-owner,2026-03-03T15:00:00Z,ctr:+2%\n"
        "linkedin,li-01,exp-02,docs/index.md#day-37-big-upgrades,python -m sdetkit day36-distribution-closeout --format json,growth-owner,2026-03-03T12:00:00Z,visitors:+8%\n"
        "newsletter,nl-01,exp-03,docs/integrations-day37-experiment-lane.md,python -m sdetkit day37-experiment-lane --emit-pack-dir docs/artifacts/day37-experiment-lane-pack --format json,pm-owner,2026-03-04T09:00:00Z,replies:+1.5%\n",
    )
    _write(
        target / "day38-post-copy.md",
        "# Day 38 post copy pack\n\n"
        "## GitHub post\n"
        "- Hook: Day 37 experiment winners are now live as a repeatable distribution flow.\n"
        "- CTA docs: `docs/integrations-day37-experiment-lane.md`\n"
        "- CTA command: `python -m sdetkit day37-experiment-lane --format json --strict`\n\n"
        "## LinkedIn post\n"
        "- Hook: We translated controlled growth learnings into a deterministic posting batch.\n"
        "- CTA docs: `docs/index.md` (Day 37 + Day 38 sections)\n"
        "- CTA command: `python -m sdetkit day38-distribution-batch --format json --strict`\n\n"
        "## Newsletter blurb\n"
        "- Hook: Day 38 moves from experiments to coordinated execution with quality guardrails.\n"
        "- CTA docs: `docs/integrations-day38-distribution-batch.md`\n"
        "- CTA command: `python -m sdetkit day38-distribution-batch --emit-pack-dir docs/artifacts/day38-distribution-batch-pack --format json --strict`\n",
    )
    _write(
        target / "day38-kpi-scorecard.json",
        json.dumps(
            {
                "generated_for": "day38-distribution-batch",
                "channels": [
                    {
                        "channel": "github",
                        "kpi": "readme_to_command_ctr",
                        "baseline": 3.4,
                        "current": 3.6,
                        "delta_pct": 5.88,
                    },
                    {
                        "channel": "linkedin",
                        "kpi": "docs_unique_visitors",
                        "baseline": 776,
                        "current": 825,
                        "delta_pct": 6.31,
                    },
                    {
                        "channel": "newsletter",
                        "kpi": "reply_rate",
                        "baseline": 1.52,
                        "current": 1.61,
                        "delta_pct": 5.92,
                    },
                ],
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "day38-execution-log.md",
        "# Day 38 execution log\n\n"
        "- [ ] 2026-03-03: Publish GitHub + LinkedIn posts with docs + command CTAs.\n"
        "- [ ] 2026-03-04: Publish newsletter segment and capture first 24h KPI pulse.\n"
        "- [ ] 2026-03-05: Record winners/misses and map Day 39 playbook priorities.\n",
    )
    _write(
        target / "day38-delivery-board.md",
        "# Day 38 delivery board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day38-validation-commands.md",
        "# Day 38 validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
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
        "name": "day38-distribution-batch-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "day38-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 38 distribution batch scorer.")
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
            _write(page, _DAY38_DEFAULT_PAGE)

    payload = build_day38_distribution_batch_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day38-distribution-batch-pack/evidence")
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
