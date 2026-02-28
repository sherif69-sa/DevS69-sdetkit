from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day30-phase1-wrap.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_SECTION_HEADER = "# Day 30 \u2014 Phase-1 wrap and Phase-2 handoff"
_REQUIRED_SECTIONS = [
    "## Why Day 30 matters",
    "## Required inputs (Days 27-29)",
    "## Day 30 command lane",
    "## Scoring model",
    "## Locked Phase-2 backlog",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day30-phase1-wrap --format json --strict",
    "python -m sdetkit day30-phase1-wrap --emit-pack-dir docs/artifacts/day30-wrap-pack --format json --strict",
    "python -m sdetkit day30-phase1-wrap --execute --evidence-dir docs/artifacts/day30-wrap-pack/evidence --format json --strict",
    "python scripts/check_day30_phase1_wrap_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day30-phase1-wrap --format json --strict",
    "python scripts/check_day30_phase1_wrap_contract.py --skip-evidence",
]

_DAY30_DEFAULT_PAGE = """# Day 30 \u2014 Phase-1 wrap and Phase-2 handoff

Day 30 closes Phase-1 with a hard evidence wrap-up and locks the first Phase-2 execution backlog.

## Why Day 30 matters

- Consolidates readiness results from Days 27-29 into a single handoff packet.
- Prevents ambiguous next steps by publishing a deterministic Phase-2 backlog contract.
- Produces an auditable launch artifact for maintainers and collaborators.

## Required inputs (Days 27-29)

- `docs/artifacts/day27-kpi-pack/day27-kpi-summary.json`
- `docs/artifacts/day28-weekly-pack/day28-weekly-review-summary.json`
- `docs/artifacts/day29-hardening-pack/day29-phase1-hardening-summary.json`

## Day 30 command lane

```bash
python -m sdetkit day30-phase1-wrap --format json --strict
python -m sdetkit day30-phase1-wrap --emit-pack-dir docs/artifacts/day30-wrap-pack --format json --strict
python -m sdetkit day30-phase1-wrap --execute --evidence-dir docs/artifacts/day30-wrap-pack/evidence --format json --strict
python scripts/check_day30_phase1_wrap_contract.py
```

## Scoring model

Day 30 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability and strategy alignment (README/docs index/top-10): 25 points.
- Input artifact availability (Days 27-29): 25 points.
- Locked Phase-2 backlog quality: 20 points.

## Locked Phase-2 backlog

- [ ] Day 31 baseline metrics + weekly targets
- [ ] Day 32 release cadence + changelog checklist
- [ ] Day 33 demo asset #1 (doctor)
- [ ] Day 34 demo asset #2 (repo audit)
- [ ] Day 35 weekly review #5
- [ ] Day 36 demo asset #3 (security gate)
- [ ] Day 37 demo asset #4 (cassette replay)
- [ ] Day 38 distribution batch #1
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


def build_day30_phase1_wrap_summary(
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

    day27_path = root / "docs/artifacts/day27-kpi-pack/day27-kpi-summary.json"
    day28_path = root / "docs/artifacts/day28-weekly-pack/day28-weekly-review-summary.json"
    day29_path = root / "docs/artifacts/day29-hardening-pack/day29-phase1-hardening-summary.json"

    day27_score, day27_ok = _load_score(day27_path)
    day28_score, day28_ok = _load_score(day28_path)
    day29_score, day29_ok = _load_score(day29_path)
    closeout_avg = (
        round((day27_score + day28_score + day29_score) / 3, 2)
        if (day27_ok and day28_ok and day29_ok)
        else 0.0
    )

    backlog_count = sum(1 for line in page_text.splitlines() if line.strip().startswith("- [ ]"))

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
            "weight": 5,
            "passed": not missing_commands,
            "evidence": {"missing_commands": missing_commands},
        },
        {
            "check_id": "readme_day30_link",
            "weight": 10,
            "passed": "docs/integrations-day30-phase1-wrap.md" in readme_text,
            "evidence": "docs/integrations-day30-phase1-wrap.md",
        },
        {
            "check_id": "readme_day30_command",
            "weight": 5,
            "passed": "day30-phase1-wrap" in readme_text,
            "evidence": "day30-phase1-wrap",
        },
        {
            "check_id": "docs_index_day30_links",
            "weight": 10,
            "passed": (
                "day-30-ultra-upgrade-report.md" in docs_index_text
                and "integrations-day30-phase1-wrap.md" in docs_index_text
            ),
            "evidence": "day-30-ultra-upgrade-report.md + integrations-day30-phase1-wrap.md",
        },
        {
            "check_id": "top10_day30_alignment",
            "weight": 5,
            "passed": (
                "Day 30 \u2014 Phase-1 wrap + handoff" in top10_text
                and "Day 31 \u2014 Phase-2 kickoff" in top10_text
            ),
            "evidence": "Day 30 + Day 31 strategy chain",
        },
        {
            "check_id": "day27_input_present",
            "weight": 8,
            "passed": day27_ok,
            "evidence": str(day27_path),
        },
        {
            "check_id": "day28_input_present",
            "weight": 8,
            "passed": day28_ok,
            "evidence": str(day28_path),
        },
        {
            "check_id": "day29_input_present",
            "weight": 8,
            "passed": day29_ok,
            "evidence": str(day29_path),
        },
        {
            "check_id": "phase2_backlog_locked",
            "weight": 20,
            "passed": backlog_count >= 8,
            "evidence": {"backlog_items": backlog_count},
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    score = round(sum(c["weight"] for c in checks if c["passed"]), 2)

    critical_failures: list[str] = []
    if missing_sections or missing_commands:
        critical_failures.append("docs_contract")
    if not (day27_ok and day28_ok and day29_ok):
        critical_failures.append("input_artifacts")
    if backlog_count < 8:
        critical_failures.append("phase2_backlog")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day27_ok and day28_ok and day29_ok:
        wins.append(f"Days 27-29 closeout artifacts loaded successfully (avg={closeout_avg}).")
    else:
        misses.append("One or more Day 27-29 artifacts are missing or malformed.")
        handoff_actions.append(
            "Regenerate Day 27-29 artifact summaries before publishing Day 30 handoff pack."
        )

    if backlog_count >= 8:
        wins.append(f"Phase-2 backlog locked with {backlog_count} actionable checklist items.")
    else:
        misses.append("Phase-2 backlog checklist is incomplete (<8 items).")
        handoff_actions.append(
            "Expand Phase-2 backlog checklist to include at least Days 31-38 action lines."
        )

    if score >= 90 and not critical_failures:
        wins.append("Day 30 wrap is release-ready and can hand off into Phase-2 kickoff.")
    else:
        handoff_actions.append(
            "Fix Day 30 docs/discoverability contract gaps and rerun strict validation."
        )

    return {
        "name": "day30-phase1-wrap",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day27_summary": str(day27_path.relative_to(root)),
            "day28_summary": str(day28_path.relative_to(root)),
            "day29_summary": str(day29_path.relative_to(root)),
        },
        "checks": checks,
        "rollup": {
            "day27_activation_score": day27_score,
            "day28_activation_score": day28_score,
            "day29_activation_score": day29_score,
            "average_activation_score": closeout_avg,
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
        "Day 30 phase-1 wrap summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Day 30 phase-1 wrap summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## Closeout rollup (Day 27-29)",
        "",
        f"- Day 27 score: `{payload['rollup']['day27_activation_score']}`",
        f"- Day 28 score: `{payload['rollup']['day28_activation_score']}`",
        f"- Day 29 score: `{payload['rollup']['day29_activation_score']}`",
        f"- Average score: `{payload['rollup']['average_activation_score']}`",
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
    _write(target / "day30-phase1-wrap-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day30-phase1-wrap-summary.md", _to_markdown(payload))
    _write(
        target / "day30-phase2-backlog.md",
        "# Locked Phase-2 backlog\n\n"
        + "\n".join(
            [
                "- [ ] " + item
                for item in [
                    "Day 31 baseline metrics + weekly targets",
                    "Day 32 release cadence + changelog checklist",
                    "Day 33 demo asset #1 (doctor)",
                    "Day 34 demo asset #2 (repo audit)",
                    "Day 35 weekly review #5",
                    "Day 36 demo asset #3 (security gate)",
                    "Day 37 demo asset #4 (cassette replay)",
                    "Day 38 distribution batch #1",
                ]
            ]
        )
        + "\n",
    )
    _write(
        target / "day30-handoff-actions.md",
        "# Day 30 handoff actions\n\n"
        + "\n".join(
            [f"- [ ] {x}" for x in payload["handoff_actions"] or ["No handoff actions required."]]
        )
        + "\n",
    )
    _write(
        target / "day30-validation-commands.md",
        "# Day 30 validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
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
        "name": "day30-phase1-wrap-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "day30-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 30 phase-1 wrap and phase-2 handoff scorer.")
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
            _write(page, _DAY30_DEFAULT_PAGE)

    payload = build_day30_phase1_wrap_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day30-wrap-pack/evidence")
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
