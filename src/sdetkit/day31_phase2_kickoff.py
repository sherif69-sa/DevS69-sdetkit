from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day31-phase2-kickoff.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY30_SUMMARY_PATH = "docs/artifacts/day30-wrap-pack/day30-phase1-wrap-summary.json"
_DAY30_BACKLOG_PATH = "docs/artifacts/day30-wrap-pack/day30-phase2-backlog.md"
_SECTION_HEADER = "# Day 31 — Phase-2 kickoff baseline"
_REQUIRED_SECTIONS = [
    "## Why Day 31 matters",
    "## Required inputs (Day 30)",
    "## Day 31 command lane",
    "## Baseline + weekly targets",
    "## Day 31 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day31-phase2-kickoff --format json --strict",
    "python -m sdetkit day31-phase2-kickoff --emit-pack-dir docs/artifacts/day31-phase2-pack --format json --strict",
    "python -m sdetkit day31-phase2-kickoff --execute --evidence-dir docs/artifacts/day31-phase2-pack/evidence --format json --strict",
    "python scripts/check_day31_phase2_kickoff_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day31-phase2-kickoff --format json --strict",
    "python -m sdetkit day31-phase2-kickoff --emit-pack-dir docs/artifacts/day31-phase2-pack --format json --strict",
    "python scripts/check_day31_phase2_kickoff_contract.py --skip-evidence",
]
_REQUIRED_WEEKLY_TARGET_LINES = [
    "Week-1 Phase-2 target: maintain activation score >= 95 and preserve strict pass.",
    "Week-1 growth target: publish 3 external-facing assets and 1 KPI checkpoint.",
    "Week-1 quality gate: every shipped action includes command evidence and a summary artifact.",
    "Week-1 decision gate: if any target misses, publish corrective actions in the next weekly review.",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 31 baseline metrics snapshot emitted",
    "- [ ] Day 32 release cadence checklist drafted",
    "- [ ] Day 33 demo asset plan (doctor) assigned",
    "- [ ] Day 34 demo asset plan (repo audit) assigned",
    "- [ ] Day 35 weekly review preparation checklist ready",
]

_DAY31_DEFAULT_PAGE = """# Day 31 — Phase-2 kickoff baseline

Day 31 starts Phase-2 with a measurable baseline carried over from Day 30 and a fixed weekly growth target set.

## Why Day 31 matters

- Converts Day 30 handoff into a measurable execution contract.
- Locks objective targets so weekly reviews can score progress without ambiguity.
- Forces evidence-backed growth planning before feature/distribution expansion.

## Required inputs (Day 30)

- `docs/artifacts/day30-wrap-pack/day30-phase1-wrap-summary.json`
- `docs/artifacts/day30-wrap-pack/day30-phase2-backlog.md`

## Day 31 command lane

```bash
python -m sdetkit day31-phase2-kickoff --format json --strict
python -m sdetkit day31-phase2-kickoff --emit-pack-dir docs/artifacts/day31-phase2-pack --format json --strict
python -m sdetkit day31-phase2-kickoff --execute --evidence-dir docs/artifacts/day31-phase2-pack/evidence --format json --strict
python scripts/check_day31_phase2_kickoff_contract.py
```

## Baseline + weekly targets

- Baseline source: Day 30 activation score and closeout rollup.
- Week-1 Phase-2 target: maintain activation score >= 95 and preserve strict pass.
- Week-1 growth target: publish 3 external-facing assets and 1 KPI checkpoint.
- Week-1 quality gate: every shipped action includes command evidence and a summary artifact.
- Week-1 decision gate: if any target misses, publish corrective actions in the next weekly review.

## Day 31 delivery board

- [ ] Day 31 baseline metrics snapshot emitted
- [ ] Day 32 release cadence checklist drafted
- [ ] Day 33 demo asset plan (doctor) assigned
- [ ] Day 34 demo asset plan (repo audit) assigned
- [ ] Day 35 weekly review preparation checklist ready

## Scoring model

Day 31 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 30 continuity and quality baseline: 35 points.
- Week-1 target and delivery board lock: 15 points.
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


def _load_day30(path: Path) -> tuple[float, bool, float]:
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
    has_day31 = any("day 31" in line for line in lines)
    has_day32 = any("day 32" in line for line in lines)
    return item_count, has_day31, has_day32


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_day31_phase2_kickoff_summary(
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
    missing_targets = _contains_all_lines(page_text, [f"- {line}" for line in _REQUIRED_WEEKLY_TARGET_LINES])
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    day30_summary = root / _DAY30_SUMMARY_PATH
    day30_backlog = root / _DAY30_BACKLOG_PATH
    day30_score, day30_strict, day30_avg = _load_day30(day30_summary)
    backlog_count, backlog_has_day31, backlog_has_day32 = _backlog_stats(day30_backlog)

    checks: list[dict[str, Any]] = [
        {"key": "docs_page_exists", "weight": 10, "passed": page_path.exists(), "evidence": str(page_path)},
        {"key": "required_sections_present", "weight": 10, "passed": not missing_sections, "evidence": {"missing_sections": missing_sections}},
        {"key": "required_commands_present", "weight": 10, "passed": not missing_commands, "evidence": {"missing_commands": missing_commands}},
        {"key": "readme_day31_link", "weight": 8, "passed": "docs/integrations-day31-phase2-kickoff.md" in readme_text, "evidence": "docs/integrations-day31-phase2-kickoff.md"},
        {"key": "readme_day31_command", "weight": 4, "passed": "day31-phase2-kickoff" in readme_text, "evidence": "day31-phase2-kickoff"},
        {"key": "docs_index_day31_links", "weight": 8, "passed": ("day-31-ultra-upgrade-report.md" in docs_index_text and "integrations-day31-phase2-kickoff.md" in docs_index_text), "evidence": "day-31-ultra-upgrade-report.md + integrations-day31-phase2-kickoff.md"},
        {"key": "top10_day31_alignment", "weight": 5, "passed": ("Day 31 — Phase-2 kickoff" in top10_text and "Day 32 — Release cadence setup" in top10_text), "evidence": "Day 31 + Day 32 strategy chain"},
        {"key": "day30_summary_present", "weight": 10, "passed": day30_summary.exists(), "evidence": str(day30_summary)},
        {"key": "day30_backlog_present", "weight": 8, "passed": day30_backlog.exists(), "evidence": str(day30_backlog)},
        {"key": "day30_quality_floor", "weight": 10, "passed": day30_strict and day30_score >= 95 and day30_avg >= 95, "evidence": {"day30_score": day30_score, "day30_average": day30_avg, "strict_pass": day30_strict}},
        {"key": "phase2_backlog_integrity", "weight": 7, "passed": backlog_count >= 8 and backlog_has_day31 and backlog_has_day32, "evidence": {"backlog_items": backlog_count, "contains_day31": backlog_has_day31, "contains_day32": backlog_has_day32}},
        {"key": "weekly_target_contract", "weight": 5, "passed": not missing_targets, "evidence": {"missing_target_lines": missing_targets}},
        {"key": "delivery_board_locked", "weight": 5, "passed": not missing_board_items, "evidence": {"missing_board_items": missing_board_items}},
    ]

    failed = [c for c in checks if not c["passed"]]
    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    critical_failures: list[str] = []
    if not day30_summary.exists() or not day30_backlog.exists():
        critical_failures.append("day30_handoff_inputs")
    if not day30_strict:
        critical_failures.append("day30_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day30_strict:
        wins.append(f"Day 30 continuity is strict-pass with score={day30_score} and avg={day30_avg}.")
    else:
        misses.append("Day 30 strict continuity signal is missing.")
        handoff_actions.append("Re-run Day 30 wrap command and restore strict pass baseline before Phase-2 expansion.")

    if backlog_count >= 8 and backlog_has_day31 and backlog_has_day32:
        wins.append(f"Phase-2 backlog integrity validated with {backlog_count} checklist items.")
    else:
        misses.append("Phase-2 backlog integrity is incomplete (needs >=8 items and Day 31/32 anchors).")
        handoff_actions.append("Repair Day 30 backlog to include at least 8 items with explicit Day 31 and Day 32 lines.")

    if not missing_targets and not missing_board_items:
        wins.append("Week-1 targets and Day 31 delivery board are fully locked.")
    else:
        misses.append("Week-1 target contract or delivery board entries are missing.")
        handoff_actions.append("Complete all Day 31 target lines and delivery board checklist entries in integration docs.")

    if not failed and not critical_failures:
        wins.append("Day 31 kickoff is fully closed and ready for Day 32 release-cadence execution.")

    return {
        "name": "day31-phase2-kickoff",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day30_summary": str(day30_summary.relative_to(root)) if day30_summary.exists() else str(day30_summary),
            "day30_backlog": str(day30_backlog.relative_to(root)) if day30_backlog.exists() else str(day30_backlog),
        },
        "checks": checks,
        "rollup": {
            "day30_activation_score": day30_score,
            "day30_average_activation_score": day30_avg,
            "day30_backlog_items": backlog_count,
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
        "Day 31 phase-2 kickoff summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Day 31 phase-2 kickoff summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## Day 30 continuity",
        "",
        f"- Day 30 activation score: `{payload['rollup']['day30_activation_score']}`",
        f"- Day 30 average activation score: `{payload['rollup']['day30_average_activation_score']}`",
        f"- Day 30 backlog checklist items: `{payload['rollup']['day30_backlog_items']}`",
        "",
        "## Wins",
    ]
    lines.extend(f"- {item}" for item in payload["wins"])
    lines.append("\n## Misses")
    lines.extend(f"- {item}" for item in payload["misses"] or ["No misses recorded."])
    lines.append("\n## Handoff actions")
    lines.extend(f"- [ ] {item}" for item in payload["handoff_actions"] or ["No handoff actions required."])
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _emit_pack(root: Path, payload: dict[str, Any], pack_dir: Path) -> None:
    target = (root / pack_dir).resolve() if not pack_dir.is_absolute() else pack_dir
    target.mkdir(parents=True, exist_ok=True)
    _write(target / "day31-phase2-kickoff-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day31-phase2-kickoff-summary.md", _to_markdown(payload))
    _write(
        target / "day31-baseline-snapshot.json",
        json.dumps(
            {
                "day": 31,
                "baseline": {
                    "day30_activation_score": payload["rollup"]["day30_activation_score"],
                    "day30_average_activation_score": payload["rollup"]["day30_average_activation_score"],
                    "day30_backlog_items": payload["rollup"]["day30_backlog_items"],
                },
                "week1_targets": {
                    "activation_score_floor": 95,
                    "external_assets": 3,
                    "kpi_checkpoints": 1,
                },
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "day31-delivery-board.md",
        "# Day 31 delivery board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(target / "day31-validation-commands.md", "# Day 31 validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n")


def _run_execution(root: Path, evidence_dir: Path) -> None:
    target = (root / evidence_dir).resolve() if not evidence_dir.is_absolute() else evidence_dir
    target.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    for command in _EXECUTION_COMMANDS:
        proc = subprocess.run(shlex.split(command), cwd=root, text=True, capture_output=True, check=False)
        logs.append({"command": command, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
    summary = {
        "name": "day31-phase2-kickoff-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "day31-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 31 phase-2 kickoff baseline scorer.")
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
            _write(page, _DAY31_DEFAULT_PAGE)

    payload = build_day31_phase2_kickoff_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = Path(ns.evidence_dir) if ns.evidence_dir else Path("docs/artifacts/day31-phase2-pack/evidence")
        _run_execution(root, ev_dir)

    if ns.format == "json":
        rendered = json.dumps(payload, indent=2) + "\n"
    elif ns.format == "markdown":
        rendered = _to_markdown(payload)
    else:
        rendered = _to_text(payload)

    if ns.output:
        _write((root / ns.output).resolve() if not Path(ns.output).is_absolute() else Path(ns.output), rendered)
    else:
        print(rendered, end="")

    if ns.strict and (payload["summary"]["failed_checks"] > 0 or payload["summary"]["critical_failures"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
