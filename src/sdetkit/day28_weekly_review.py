from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day28-weekly-review.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_SECTION_HEADER = "# Weekly review #4 (Day 28)"
_REQUIRED_SECTIONS = [
    "## Who should run Day 28",
    "## Inputs from Days 25-27",
    "## Closeout checklist",
    "## Scoring model",
    "## Evidence mode",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day28-weekly-review --format json --strict",
    "python -m sdetkit day28-weekly-review --emit-pack-dir docs/artifacts/day28-weekly-pack --format json --strict",
    "python -m sdetkit day28-weekly-review --execute --evidence-dir docs/artifacts/day28-weekly-pack/evidence --format json --strict",
    "python scripts/check_day28_weekly_review_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day28-weekly-review --format json --strict",
    "python scripts/check_day28_weekly_review_contract.py --skip-evidence",
]

_DAY28_DEFAULT_PAGE = """# Weekly review #4 (Day 28)

Day 28 closes the weekly growth loop by consolidating Day 25-27 outcomes into wins, misses, and corrective actions.

## Who should run Day 28

- Maintainers preparing Phase-1 closeout and Day 29 hardening priorities.
- DevRel/community operators validating that activation efforts converted to contributions.
- Engineering managers requiring an auditable weekly checkpoint before handoff.

## Inputs from Days 25-27

- Day 25: `docs/artifacts/day25-community-pack/day25-community-summary.json`
- Day 26: `docs/artifacts/day26-external-contribution-pack/day26-external-contribution-summary.json`
- Day 27: `docs/artifacts/day27-kpi-pack/day27-kpi-summary.json`

## Closeout checklist

```bash
python -m sdetkit day28-weekly-review --format json --strict
python -m sdetkit day28-weekly-review --emit-pack-dir docs/artifacts/day28-weekly-pack --format json --strict
python -m sdetkit day28-weekly-review --execute --evidence-dir docs/artifacts/day28-weekly-pack/evidence --format json --strict
python scripts/check_day28_weekly_review_contract.py
```

## Scoring model

Day 28 weighted score (0-100):

- Docs contract + command lane completeness: 40 points.
- Discoverability links in README/docs index: 20 points.
- Roadmap alignment and closeout language quality: 15 points.
- Input artifact availability from Days 25-27: 25 points.

## Evidence mode

`--execute` runs deterministic checks and captures command logs in `--evidence-dir`.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_score(path: Path) -> tuple[float, bool]:
    if not path.exists():
        return 0.0, False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0.0, False
    summary = data.get("summary") if isinstance(data, dict) else None
    score = summary.get("activation_score") if isinstance(summary, dict) else None
    if isinstance(score, (int, float)):
        return float(score), True
    return 0.0, False


def build_day28_weekly_review_summary(
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

    day25_path = root / "docs/artifacts/day25-community-pack/day25-community-summary.json"
    day26_path = (
        root
        / "docs/artifacts/day26-external-contribution-pack/day26-external-contribution-summary.json"
    )
    day27_path = root / "docs/artifacts/day27-kpi-pack/day27-kpi-summary.json"

    day25_score, day25_ok = _load_score(day25_path)
    day26_score, day26_ok = _load_score(day26_path)
    day27_score, day27_ok = _load_score(day27_path)
    rollup_avg = (
        round((day25_score + day26_score + day27_score) / 3, 2)
        if (day25_ok and day26_ok and day27_ok)
        else 0.0
    )

    checks: list[dict[str, Any]] = [
        {
            "check_id": "docs_page_exists",
            "category": "contract",
            "weight": 10,
            "passed": page_path.exists(),
            "evidence": str(page_path),
        },
        {
            "check_id": "required_sections_present",
            "category": "contract",
            "weight": 20,
            "passed": not missing_sections,
            "evidence": {"missing_sections": missing_sections},
        },
        {
            "check_id": "required_commands_present",
            "category": "contract",
            "weight": 10,
            "passed": not missing_commands,
            "evidence": {"missing_commands": missing_commands},
        },
        {
            "check_id": "readme_day28_link",
            "category": "discoverability",
            "weight": 10,
            "passed": "docs/integrations-day28-weekly-review.md" in readme_text,
            "evidence": "docs/integrations-day28-weekly-review.md",
        },
        {
            "check_id": "docs_index_day28_link",
            "category": "discoverability",
            "weight": 10,
            "passed": "day-28-ultra-upgrade-report.md" in docs_index_text,
            "evidence": "day-28-ultra-upgrade-report.md",
        },
        {
            "check_id": "top10_day28_alignment",
            "category": "strategy",
            "weight": 8,
            "passed": "Day 28 \u2014 Weekly review #4" in top10_text,
            "evidence": "Day 28 \u2014 Weekly review #4",
        },
        {
            "check_id": "docs_mentions_wins_misses_actions",
            "category": "strategy",
            "weight": 7,
            "passed": all(word in page_text.lower() for word in ["wins", "misses", "corrective"]),
            "evidence": "wins/misses/corrective",
        },
        {
            "check_id": "day25_input_present",
            "category": "data",
            "weight": 8,
            "passed": day25_ok,
            "evidence": str(day25_path),
        },
        {
            "check_id": "day26_input_present",
            "category": "data",
            "weight": 8,
            "passed": day26_ok,
            "evidence": str(day26_path),
        },
        {
            "check_id": "day27_input_present",
            "category": "data",
            "weight": 9,
            "passed": day27_ok,
            "evidence": str(day27_path),
        },
    ]

    failed = [item for item in checks if not item["passed"]]
    critical = {
        "docs_page_exists",
        "required_sections_present",
        "required_commands_present",
        "top10_day28_alignment",
    }
    critical_failures = [item["check_id"] for item in failed if item["check_id"] in critical]

    total_weight = sum(int(item["weight"]) for item in checks)
    earned_weight = sum(int(item["weight"]) for item in checks if item["passed"])
    score = round((earned_weight / total_weight) * 100, 2) if total_weight else 0.0

    wins: list[str] = []
    misses: list[str] = []
    corrective_actions: list[str] = []
    if day25_ok and day25_score >= 90:
        wins.append(f"Day 25 community activation remained strong ({day25_score}).")
    else:
        misses.append("Day 25 summary missing or below closeout target.")
        corrective_actions.append(
            "Re-run Day 25 pack generation and restore summary JSON for traceability."
        )
    if day26_ok and day26_score >= 90:
        wins.append(f"Day 26 external contribution push stayed healthy ({day26_score}).")
    else:
        misses.append("Day 26 summary missing or below closeout target.")
        corrective_actions.append(
            "Re-run Day 26 strict lane and publish updated external contribution summary."
        )
    if day27_ok and day27_score >= 90:
        wins.append(f"Day 27 KPI audit preserved positive momentum ({day27_score}).")
    else:
        misses.append("Day 27 KPI summary missing or below closeout target.")
        corrective_actions.append(
            "Refresh KPI baseline/current snapshots and regenerate Day 27 artifacts."
        )

    if score >= 90 and not critical_failures:
        wins.append("Day 28 weekly review #4 is ready for final phase-close communication.")
    else:
        corrective_actions.append(
            "Address Day 28 documentation and discoverability gaps before phase closeout."
        )

    return {
        "name": "day28-weekly-review",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day25_summary": str(day25_path.relative_to(root)),
            "day26_summary": str(day26_path.relative_to(root)),
            "day27_summary": str(day27_path.relative_to(root)),
        },
        "checks": checks,
        "rollup": {
            "day25_activation_score": day25_score,
            "day26_activation_score": day26_score,
            "day27_activation_score": day27_score,
            "average_activation_score": rollup_avg,
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
        "corrective_actions": corrective_actions,
    }


def _to_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return (
        "Day 28 weekly review summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Day 28 weekly review summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## KPI rollup (Day 25-27)",
        "",
        f"- Day 25 score: `{payload['rollup']['day25_activation_score']}`",
        f"- Day 26 score: `{payload['rollup']['day26_activation_score']}`",
        f"- Day 27 score: `{payload['rollup']['day27_activation_score']}`",
        f"- Average score: `{payload['rollup']['average_activation_score']}`",
        "",
        "## Wins",
    ]
    lines.extend(f"- {item}" for item in payload["wins"])
    lines.append("\n## Misses")
    lines.extend(f"- {item}" for item in payload["misses"] or ["No misses recorded."])
    lines.append("\n## Corrective actions")
    lines.extend(
        f"- [ ] {item}"
        for item in payload["corrective_actions"] or ["No corrective actions required."]
    )
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _emit_pack(root: Path, payload: dict[str, Any], pack_dir: Path) -> None:
    target = (root / pack_dir).resolve() if not pack_dir.is_absolute() else pack_dir
    target.mkdir(parents=True, exist_ok=True)
    _write(target / "day28-weekly-review-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day28-kpi-rollup.md", _to_markdown(payload))
    _write(
        target / "day28-wins-misses-actions.md",
        "# Day 28 wins, misses, and corrective actions\n\n"
        + "\n".join(
            [
                "## Wins",
                *[f"- {x}" for x in payload["wins"]],
                "",
                "## Misses",
                *[f"- {x}" for x in payload["misses"] or ["No misses recorded."]],
                "",
                "## Corrective actions",
                *[
                    f"- [ ] {x}"
                    for x in payload["corrective_actions"] or ["No corrective actions required."]
                ],
            ]
        )
        + "\n",
    )
    _write(
        target / "day28-validation-commands.md",
        "# Day 28 validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
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
        "name": "day28-weekly-review-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "day28-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 28 weekly review closeout scorer.")
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
            _write(page, _DAY28_DEFAULT_PAGE)

    payload = build_day28_weekly_review_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day28-weekly-pack/evidence")
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
