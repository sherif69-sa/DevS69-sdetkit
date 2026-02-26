from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day37-experiment-lane.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY36_SUMMARY_PATH = (
    "docs/artifacts/day36-distribution-closeout-pack/day36-distribution-closeout-summary.json"
)
_DAY36_BOARD_PATH = "docs/artifacts/day36-distribution-closeout-pack/day36-delivery-board.md"
_SECTION_HEADER = "# Day 37 — Experiment lane activation"
_REQUIRED_SECTIONS = [
    "## Why Day 37 matters",
    "## Required inputs (Day 36)",
    "## Day 37 command lane",
    "## Experiment contract",
    "## Experiment quality checklist",
    "## Day 37 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day37-experiment-lane --format json --strict",
    "python -m sdetkit day37-experiment-lane --emit-pack-dir docs/artifacts/day37-experiment-lane-pack --format json --strict",
    "python -m sdetkit day37-experiment-lane --execute --evidence-dir docs/artifacts/day37-experiment-lane-pack/evidence --format json --strict",
    "python scripts/check_day37_experiment_lane_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day37-experiment-lane --format json --strict",
    "python -m sdetkit day37-experiment-lane --emit-pack-dir docs/artifacts/day37-experiment-lane-pack --format json --strict",
    "python scripts/check_day37_experiment_lane_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for experiment execution and decision logging.",
    "At least three experiments include hypothesis, KPI target delta, and stop/continue threshold.",
    "Every experiment is linked to one Day 36 distribution miss with explicit remediation intent.",
    "Day 37 report commits Day 38 distribution batch actions based on experiment outcomes.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes at least three experiments with control vs variant definitions",
    "- [ ] Every experiment has KPI target, owner, and decision deadline",
    "- [ ] Guardrail metrics include reliability and contribution-quality checks",
    "- [ ] Experiment scorecard records baseline, current, and delta fields",
    "- [ ] Artifact pack includes matrix, hypothesis brief, scorecard, and decision log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 37 experiment matrix committed",
    "- [ ] Day 37 hypothesis brief reviewed with owner + backup",
    "- [ ] Day 37 scorecard snapshot exported",
    "- [ ] Day 38 distribution batch actions selected from winners",
    "- [ ] Day 38 fallback plan documented for losing variants",
]

_DAY37_DEFAULT_PAGE = """# Day 37 — Experiment lane activation

Day 37 turns Day 36 distribution misses into controlled experiments with strict scoring, owner accountability, and Day 38 rollout decisions.

## Why Day 37 matters

- Converts distribution misses into measurable learnings instead of ad-hoc retries.
- Protects quality by coupling growth experiments to reliability and contribution guardrails.
- Creates a deterministic handoff from experiment outcomes into Day 38 distribution actions.

## Required inputs (Day 36)

- `docs/artifacts/day36-distribution-closeout-pack/day36-distribution-closeout-summary.json`
- `docs/artifacts/day36-distribution-closeout-pack/day36-delivery-board.md`

## Day 37 command lane

```bash
python -m sdetkit day37-experiment-lane --format json --strict
python -m sdetkit day37-experiment-lane --emit-pack-dir docs/artifacts/day37-experiment-lane-pack --format json --strict
python -m sdetkit day37-experiment-lane --execute --evidence-dir docs/artifacts/day37-experiment-lane-pack/evidence --format json --strict
python scripts/check_day37_experiment_lane_contract.py
```

## Experiment contract

- Single owner + backup reviewer are assigned for experiment execution and decision logging.
- At least three experiments include hypothesis, KPI target delta, and stop/continue threshold.
- Every experiment is linked to one Day 36 distribution miss with explicit remediation intent.
- Day 37 report commits Day 38 distribution batch actions based on experiment outcomes.

## Experiment quality checklist

- [ ] Includes at least three experiments with control vs variant definitions
- [ ] Every experiment has KPI target, owner, and decision deadline
- [ ] Guardrail metrics include reliability and contribution-quality checks
- [ ] Experiment scorecard records baseline, current, and delta fields
- [ ] Artifact pack includes matrix, hypothesis brief, scorecard, and decision log

## Day 37 delivery board

- [ ] Day 37 experiment matrix committed
- [ ] Day 37 hypothesis brief reviewed with owner + backup
- [ ] Day 37 scorecard snapshot exported
- [ ] Day 38 distribution batch actions selected from winners
- [ ] Day 38 fallback plan documented for losing variants

## Scoring model

Day 37 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 36 continuity and strict baseline carryover: 35 points.
- Experiment contract lock + delivery board readiness: 15 points.
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


def _load_day36(path: Path) -> tuple[float, bool, int]:
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
    has_day36 = any("day 36" in line for line in lines)
    has_day37 = any("day 37" in line for line in lines)
    return item_count, has_day36, has_day37


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_day37_experiment_lane_summary(
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

    day36_summary = root / _DAY36_SUMMARY_PATH
    day36_board = root / _DAY36_BOARD_PATH
    day36_score, day36_strict, day36_check_count = _load_day36(day36_summary)
    board_count, board_has_day36, board_has_day37 = _board_stats(day36_board)

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
            "check_id": "readme_day37_link",
            "weight": 8,
            "passed": "docs/integrations-day37-experiment-lane.md" in readme_text,
            "evidence": "docs/integrations-day37-experiment-lane.md",
        },
        {
            "check_id": "readme_day37_command",
            "weight": 4,
            "passed": "day37-experiment-lane" in readme_text,
            "evidence": "day37-experiment-lane",
        },
        {
            "check_id": "docs_index_day37_links",
            "weight": 8,
            "passed": (
                "day-37-big-upgrade-report.md" in docs_index_text
                and "integrations-day37-experiment-lane.md" in docs_index_text
            ),
            "evidence": "day-37-big-upgrade-report.md + integrations-day37-experiment-lane.md",
        },
        {
            "check_id": "top10_day37_alignment",
            "weight": 5,
            "passed": ("Day 37" in top10_text and "Day 38" in top10_text),
            "evidence": "Day 37 + Day 38 strategy chain",
        },
        {
            "check_id": "day36_summary_present",
            "weight": 10,
            "passed": day36_summary.exists(),
            "evidence": str(day36_summary),
        },
        {
            "check_id": "day36_delivery_board_present",
            "weight": 8,
            "passed": day36_board.exists(),
            "evidence": str(day36_board),
        },
        {
            "check_id": "day36_quality_floor",
            "weight": 10,
            "passed": day36_strict and day36_score >= 95,
            "evidence": {
                "day36_score": day36_score,
                "strict_pass": day36_strict,
                "day36_checks": day36_check_count,
            },
        },
        {
            "check_id": "day36_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day36 and board_has_day37,
            "evidence": {
                "board_items": board_count,
                "contains_day36": board_has_day36,
                "contains_day37": board_has_day37,
            },
        },
        {
            "check_id": "experiment_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "experiment_quality_checklist_locked",
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
    if not day36_summary.exists() or not day36_board.exists():
        critical_failures.append("day36_handoff_inputs")
    if not day36_strict:
        critical_failures.append("day36_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day36_strict:
        wins.append(f"Day 36 continuity is strict-pass with activation score={day36_score}.")
    else:
        misses.append("Day 36 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 36 distribution closeout command and restore strict pass baseline before Day 37 lock."
        )

    if board_count >= 5 and board_has_day36 and board_has_day37:
        wins.append(
            f"Day 36 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 36 delivery board integrity is incomplete (needs >=5 items and Day 36/37 anchors)."
        )
        handoff_actions.append(
            "Repair Day 36 delivery board entries to include Day 36 and Day 37 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Experiment contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Experiment contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 37 experiment contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 37 experiment lane activation is fully complete and ready for Day 38 distribution batch #1."
        )

    return {
        "name": "day37-experiment-lane",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day36_summary": str(day36_summary.relative_to(root))
            if day36_summary.exists()
            else str(day36_summary),
            "day36_delivery_board": str(day36_board.relative_to(root))
            if day36_board.exists()
            else str(day36_board),
        },
        "checks": checks,
        "rollup": {
            "day36_activation_score": day36_score,
            "day36_checks": day36_check_count,
            "day36_delivery_board_items": board_count,
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
        "Day 37 experiment lane summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Day 37 experiment lane summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## Day 36 continuity",
        "",
        f"- Day 36 activation score: `{payload['rollup']['day36_activation_score']}`",
        f"- Day 36 checks evaluated: `{payload['rollup']['day36_checks']}`",
        f"- Day 36 delivery board checklist items: `{payload['rollup']['day36_delivery_board_items']}`",
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
    _write(target / "day37-experiment-lane-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day37-experiment-lane-summary.md", _to_markdown(payload))
    _write(
        target / "day37-experiment-matrix.csv",
        "experiment_id,distribution_miss,control,variant,kpi_target,stop_threshold,owner,decision_deadline\n"
        "exp-01,github_hook_ctr_low,narrative-first,command-first,readme_to_command_ctr:+2%,<0.5% uplift,community-owner,2026-03-01\n"
        "exp-02,linkedin_post_timing_miss,afternoon_slot,morning_slot,docs_unique_visitors:+8%,engagement<-5%,growth-owner,2026-03-01\n"
        "exp-03,newsletter_reply_rate_flat,text-only,teaser-gif,newsletter_reply_rate:+1.5%,unsubscribe>0.2%,pm-owner,2026-03-01\n",
    )
    _write(
        target / "day37-hypothesis-brief.md",
        "# Day 37 experiment hypothesis brief\n\n"
        "## Experiment hypotheses\n"
        "- `exp-01`: Command-first headline improves contributor command CTR by at least 2%.\n"
        "- `exp-02`: Morning posting window improves docs unique visitors by at least 8%.\n"
        "- `exp-03`: GIF teaser improves newsletter reply rate by at least 1.5%.\n\n"
        "## Guardrails\n"
        "- Reliability: no increase in flaky or failing pipeline runs linked to experiment traffic.\n"
        "- Contribution quality: no drop in first-pass review acceptance rate beyond 3%.\n",
    )
    _write(
        target / "day37-experiment-scorecard.json",
        json.dumps(
            {
                "generated_for": "day37-experiment-lane",
                "experiments": [
                    {
                        "experiment_id": "exp-01",
                        "kpi": "readme_to_command_ctr",
                        "baseline": 3.1,
                        "current": 3.4,
                        "delta_pct": 9.68,
                        "status": "running",
                    },
                    {
                        "experiment_id": "exp-02",
                        "kpi": "docs_unique_visitors",
                        "baseline": 740,
                        "current": 776,
                        "delta_pct": 4.86,
                        "status": "running",
                    },
                    {
                        "experiment_id": "exp-03",
                        "kpi": "newsletter_reply_rate",
                        "baseline": 1.4,
                        "current": 1.52,
                        "delta_pct": 8.57,
                        "status": "running",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "day37-decision-log.md",
        "# Day 37 decision log\n\n"
        "- [ ] 2026-03-01: Promote winning variant(s) into Day 38 distribution batch #1.\n"
        "- [ ] 2026-03-01: Pause losing variant(s) and record fallback plan.\n"
        "- [ ] 2026-03-02: Publish day37 closeout summary with Day 38 rollout checklist.\n",
    )
    _write(
        target / "day37-delivery-board.md",
        "# Day 37 delivery board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day37-validation-commands.md",
        "# Day 37 validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
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
        "name": "day37-experiment-lane-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "day37-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 37 experiment lane activation scorer.")
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
            _write(page, _DAY37_DEFAULT_PAGE)

    payload = build_day37_experiment_lane_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day37-experiment-lane-pack/evidence")
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
