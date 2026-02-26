from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day32-release-cadence.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY31_SUMMARY_PATH = "docs/artifacts/day31-phase2-pack/day31-phase2-kickoff-summary.json"
_DAY31_BOARD_PATH = "docs/artifacts/day31-phase2-pack/day31-delivery-board.md"
_SECTION_HEADER = "# Day 32 — Release cadence setup"
_REQUIRED_SECTIONS = [
    "## Why Day 32 matters",
    "## Required inputs (Day 31)",
    "## Day 32 command lane",
    "## Weekly cadence contract",
    "## Changelog quality checklist",
    "## Day 32 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day32-release-cadence --format json --strict",
    "python -m sdetkit day32-release-cadence --emit-pack-dir docs/artifacts/day32-release-cadence-pack --format json --strict",
    "python -m sdetkit day32-release-cadence --execute --evidence-dir docs/artifacts/day32-release-cadence-pack/evidence --format json --strict",
    "python scripts/check_day32_release_cadence_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day32-release-cadence --format json --strict",
    "python -m sdetkit day32-release-cadence --emit-pack-dir docs/artifacts/day32-release-cadence-pack --format json --strict",
    "python scripts/check_day32_release_cadence_contract.py --skip-evidence",
]
_REQUIRED_CADENCE_LINES = [
    "Cadence owner: release captain rotates weekly and is published in advance.",
    "Cadence rhythm: every Friday publish changelog, release narrative, and proof links.",
    "Cadence SLA: release artifact pack emitted within 60 minutes of merge cutoff.",
    "Rollback gate: if quality score < 95, postpone release and publish corrective actions.",
]
_REQUIRED_CHANGELOG_LINES = [
    "- [ ] Summary includes user-facing outcomes, not only internal refactors",
    "- [ ] Every major change links to docs or runnable command evidence",
    "- [ ] Breaking/risky changes include mitigation and rollback notes",
    "- [ ] KPI movement for the week is captured in release notes",
    "- [ ] Follow-up backlog items are explicitly listed with owners",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 32 cadence calendar committed",
    "- [ ] Day 32 changelog template committed",
    "- [ ] Day 33 demo asset #1 scope frozen",
    "- [ ] Day 34 demo asset #2 scope frozen",
    "- [ ] Day 35 weekly review KPI frame locked",
]

_DAY32_DEFAULT_PAGE = """# Day 32 — Release cadence setup

Day 32 converts Day 31 baseline goals into a repeatable release operating cadence with a strict changelog quality gate.

## Why Day 32 matters

- Locks a weekly release rhythm that keeps growth loops predictable.
- Standardizes changelog quality so every release is user-legible and evidence-backed.
- Prevents rushed release drops by enforcing rollback and corrective-action rules.

## Required inputs (Day 31)

- `docs/artifacts/day31-phase2-pack/day31-phase2-kickoff-summary.json`
- `docs/artifacts/day31-phase2-pack/day31-delivery-board.md`

## Day 32 command lane

```bash
python -m sdetkit day32-release-cadence --format json --strict
python -m sdetkit day32-release-cadence --emit-pack-dir docs/artifacts/day32-release-cadence-pack --format json --strict
python -m sdetkit day32-release-cadence --execute --evidence-dir docs/artifacts/day32-release-cadence-pack/evidence --format json --strict
python scripts/check_day32_release_cadence_contract.py
```

## Weekly cadence contract

- Cadence owner: release captain rotates weekly and is published in advance.
- Cadence rhythm: every Friday publish changelog, release narrative, and proof links.
- Cadence SLA: release artifact pack emitted within 60 minutes of merge cutoff.
- Rollback gate: if quality score < 95, postpone release and publish corrective actions.

## Changelog quality checklist

- [ ] Summary includes user-facing outcomes, not only internal refactors
- [ ] Every major change links to docs or runnable command evidence
- [ ] Breaking/risky changes include mitigation and rollback notes
- [ ] KPI movement for the week is captured in release notes
- [ ] Follow-up backlog items are explicitly listed with owners

## Day 32 delivery board

- [ ] Day 32 cadence calendar committed
- [ ] Day 32 changelog template committed
- [ ] Day 33 demo asset #1 scope frozen
- [ ] Day 34 demo asset #2 scope frozen
- [ ] Day 35 weekly review KPI frame locked

## Scoring model

Day 32 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 31 continuity and strict baseline carryover: 35 points.
- Cadence/changelog contract lock + delivery board readiness: 15 points.
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


def _load_day31(path: Path) -> tuple[float, bool, int]:
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
    has_day32 = any("day 32" in line for line in lines)
    has_day33 = any("day 33" in line for line in lines)
    return item_count, has_day32, has_day33


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_day32_release_cadence_summary(
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
    missing_cadence_lines = _contains_all_lines(
        page_text, [f"- {line}" for line in _REQUIRED_CADENCE_LINES]
    )
    missing_changelog_lines = _contains_all_lines(page_text, _REQUIRED_CHANGELOG_LINES)
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    day31_summary = root / _DAY31_SUMMARY_PATH
    day31_board = root / _DAY31_BOARD_PATH
    day31_score, day31_strict, day31_check_count = _load_day31(day31_summary)
    board_count, board_has_day32, board_has_day33 = _board_stats(day31_board)

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
            "check_id": "readme_day32_link",
            "weight": 8,
            "passed": "docs/integrations-day32-release-cadence.md" in readme_text,
            "evidence": "docs/integrations-day32-release-cadence.md",
        },
        {
            "check_id": "readme_day32_command",
            "weight": 4,
            "passed": "day32-release-cadence" in readme_text,
            "evidence": "day32-release-cadence",
        },
        {
            "check_id": "docs_index_day32_links",
            "weight": 8,
            "passed": (
                "day-32-ultra-upgrade-report.md" in docs_index_text
                and "integrations-day32-release-cadence.md" in docs_index_text
            ),
            "evidence": "day-32-ultra-upgrade-report.md + integrations-day32-release-cadence.md",
        },
        {
            "check_id": "top10_day32_alignment",
            "weight": 5,
            "passed": (
                "Day 32 — Release cadence setup" in top10_text
                and "Day 33 — Demo asset #1" in top10_text
            ),
            "evidence": "Day 32 + Day 33 strategy chain",
        },
        {
            "check_id": "day31_summary_present",
            "weight": 10,
            "passed": day31_summary.exists(),
            "evidence": str(day31_summary),
        },
        {
            "check_id": "day31_delivery_board_present",
            "weight": 8,
            "passed": day31_board.exists(),
            "evidence": str(day31_board),
        },
        {
            "check_id": "day31_quality_floor",
            "weight": 10,
            "passed": day31_strict and day31_score >= 95,
            "evidence": {
                "day31_score": day31_score,
                "strict_pass": day31_strict,
                "day31_checks": day31_check_count,
            },
        },
        {
            "check_id": "day31_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day32 and board_has_day33,
            "evidence": {
                "board_items": board_count,
                "contains_day32": board_has_day32,
                "contains_day33": board_has_day33,
            },
        },
        {
            "check_id": "cadence_contract_locked",
            "weight": 5,
            "passed": not missing_cadence_lines,
            "evidence": {"missing_cadence_lines": missing_cadence_lines},
        },
        {
            "check_id": "changelog_quality_checklist_locked",
            "weight": 3,
            "passed": not missing_changelog_lines,
            "evidence": {"missing_changelog_items": missing_changelog_lines},
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
    if not day31_summary.exists() or not day31_board.exists():
        critical_failures.append("day31_handoff_inputs")
    if not day31_strict:
        critical_failures.append("day31_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day31_strict:
        wins.append(f"Day 31 continuity is strict-pass with activation score={day31_score}.")
    else:
        misses.append("Day 31 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 31 kickoff command and restore strict pass baseline before release cadence lock."
        )

    if board_count >= 5 and board_has_day32 and board_has_day33:
        wins.append(
            f"Day 31 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 31 delivery board integrity is incomplete (needs >=5 items and Day 32/33 anchors)."
        )
        handoff_actions.append(
            "Repair Day 31 delivery board entries to include Day 32 and Day 33 anchors."
        )

    if not missing_cadence_lines and not missing_changelog_lines and not missing_board_items:
        wins.append("Release cadence + changelog contract is fully locked for weekly execution.")
    else:
        misses.append(
            "Cadence contract, changelog checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 32 cadence lines, changelog checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 32 release cadence setup is fully closed and ready for Day 33 demo asset execution."
        )

    return {
        "name": "day32-release-cadence",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day31_summary": str(day31_summary.relative_to(root))
            if day31_summary.exists()
            else str(day31_summary),
            "day31_delivery_board": str(day31_board.relative_to(root))
            if day31_board.exists()
            else str(day31_board),
        },
        "checks": checks,
        "rollup": {
            "day31_activation_score": day31_score,
            "day31_checks": day31_check_count,
            "day31_delivery_board_items": board_count,
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
        "Day 32 release cadence summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Day 32 release cadence summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## Day 31 continuity",
        "",
        f"- Day 31 activation score: `{payload['rollup']['day31_activation_score']}`",
        f"- Day 31 checks evaluated: `{payload['rollup']['day31_checks']}`",
        f"- Day 31 delivery board checklist items: `{payload['rollup']['day31_delivery_board_items']}`",
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
    _write(target / "day32-release-cadence-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day32-release-cadence-summary.md", _to_markdown(payload))
    _write(
        target / "day32-cadence-calendar.json",
        json.dumps(
            {
                "day": 32,
                "cadence": {
                    "publish_day": "Friday",
                    "merge_cutoff": "16:00 UTC",
                    "artifact_sla_minutes": 60,
                    "owner_rotation": "weekly",
                },
                "quality_gate": {
                    "minimum_activation_score": 95,
                    "rollback_required_below_floor": True,
                },
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "day32-changelog-template.md",
        "# Day 32 changelog template\n\n"
        "## Outcomes\n- What changed for users this week?\n\n"
        "## Evidence links\n- Commands/docs/proof artifacts\n\n"
        "## Risks and mitigations\n- Breaking changes, rollback notes\n\n"
        "## KPI movement\n- Stars, discussions, conversions, adoption notes\n\n"
        "## Follow-up backlog\n- [ ] Item + owner + ETA\n",
    )
    _write(
        target / "day32-delivery-board.md",
        "# Day 32 delivery board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day32-validation-commands.md",
        "# Day 32 validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
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
        "name": "day32-release-cadence-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "day32-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 32 release cadence setup scorer.")
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
            _write(page, _DAY32_DEFAULT_PAGE)

    payload = build_day32_release_cadence_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day32-release-cadence-pack/evidence")
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
