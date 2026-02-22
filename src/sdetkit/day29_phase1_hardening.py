from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day29-phase1-hardening.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_SECTION_HEADER = "# Day 29 — Phase-1 hardening"
_REQUIRED_SECTIONS = [
    "## Why Day 29 exists",
    "## Hardening scope",
    "## Day 29 command lane",
    "## Scoring model",
    "## Entry page polish checklist",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day29-phase1-hardening --format json --strict",
    "python -m sdetkit day29-phase1-hardening --emit-pack-dir docs/artifacts/day29-hardening-pack --format json --strict",
    "python -m sdetkit day29-phase1-hardening --execute --evidence-dir docs/artifacts/day29-hardening-pack/evidence --format json --strict",
    "python scripts/check_day29_phase1_hardening_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day29-phase1-hardening --format json --strict",
    "python scripts/check_day29_phase1_hardening_contract.py --skip-evidence",
]
_STALE_MARKERS = ["TODO", "TBD", "lorem ipsum", "coming soon"]

_DAY29_DEFAULT_PAGE = """# Day 29 — Phase-1 hardening

Day 29 closes Phase-1 by hardening top entry pages, removing stale guidance, and publishing a deterministic closeout lane.

## Why Day 29 exists

- Preserve trust by ensuring README + docs index + strategy pages are mutually consistent.
- Close stale docs gaps before Day 30 phase wrap and handoff.
- Produce a reviewable hardening artifact pack for maintainers.

## Hardening scope

- README entry-page checks and command-lane verification.
- Docs index discoverability checks for Day 29 integration/report pages.
- Strategy alignment checks against `docs/top-10-github-strategy.md` Day 29 objective.
- Stale marker scans across top entry pages and recent integration docs.

## Day 29 command lane

```bash
python -m sdetkit day29-phase1-hardening --format json --strict
python -m sdetkit day29-phase1-hardening --emit-pack-dir docs/artifacts/day29-hardening-pack --format json --strict
python -m sdetkit day29-phase1-hardening --execute --evidence-dir docs/artifacts/day29-hardening-pack/evidence --format json --strict
python scripts/check_day29_phase1_hardening_contract.py
```

## Scoring model

Day 29 weighted score (0-100):

- Docs contract and command-lane completeness: 35 points.
- Entry-page discoverability + strategy alignment: 35 points.
- Stale marker elimination in top pages: 20 points.
- Artifact/report wiring for Phase-1 closeout: 10 points.

## Entry page polish checklist

- README includes Day 29 section and command lane.
- Docs index links both integration guide and Day 29 report.
- Top-10 strategy includes Day 29 hardening objective.
- No stale placeholder markers in top entry pages.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_day29_phase1_hardening_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
) -> dict[str, Any]:
    page = root / docs_page_path
    readme = root / readme_path
    docs_index = root / docs_index_path
    top10 = root / top10_path
    report = root / "docs/day-29-ultra-upgrade-report.md"

    page_text = _read(page)
    readme_text = _read(readme)
    docs_index_text = _read(docs_index)
    top10_text = _read(top10)

    missing_sections = [s for s in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if s not in page_text]
    missing_commands = [c for c in _REQUIRED_COMMANDS if c not in page_text]

    scanned_files = {
        "README.md": readme_text,
        "docs/index.md": docs_index_text,
        "docs/top-10-github-strategy.md": top10_text,
        "docs/integrations-day29-phase1-hardening.md": page_text,
        "docs/integrations-day28-weekly-review.md": _read(
            root / "docs/integrations-day28-weekly-review.md"
        ),
    }
    stale_hits: dict[str, list[str]] = {}
    for path, text in scanned_files.items():
        hits = [marker for marker in _STALE_MARKERS if marker.lower() in text.lower()]
        if hits:
            stale_hits[path] = hits

    checks: list[dict[str, Any]] = [
        {
            "check_id": "docs_page_exists",
            "weight": 10,
            "passed": page.exists(),
            "evidence": str(page),
        },
        {
            "check_id": "required_sections_present",
            "weight": 15,
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
            "check_id": "readme_day29_link",
            "weight": 12,
            "passed": "docs/integrations-day29-phase1-hardening.md" in readme_text,
            "evidence": "docs/integrations-day29-phase1-hardening.md",
        },
        {
            "check_id": "docs_index_day29_links",
            "weight": 12,
            "passed": all(
                token in docs_index_text
                for token in [
                    "day-29-ultra-upgrade-report.md",
                    "integrations-day29-phase1-hardening.md",
                ]
            ),
            "evidence": "day-29-ultra-upgrade-report.md + integrations-day29-phase1-hardening.md",
        },
        {
            "check_id": "top10_day29_alignment",
            "weight": 11,
            "passed": "Day 29 — Phase-1 hardening" in top10_text,
            "evidence": "Day 29 — Phase-1 hardening",
        },
        {
            "check_id": "report_exists",
            "weight": 10,
            "passed": report.exists(),
            "evidence": str(report),
        },
        {
            "check_id": "stale_markers_clean",
            "weight": 20,
            "passed": not stale_hits,
            "evidence": stale_hits,
        },
    ]
    failed = [check["check_id"] for check in checks if not check["passed"]]
    score = round(sum(check["weight"] for check in checks if check["passed"]), 2)
    critical_failures = [
        name
        for name in ["docs_page_exists", "required_sections_present", "required_commands_present"]
        if name in failed
    ]

    gaps = []
    if missing_sections:
        gaps.append("Missing required Day 29 sections in integration page.")
    if missing_commands:
        gaps.append("Missing required command lane entries in integration page.")
    if stale_hits:
        gaps.append("Stale marker tokens detected across top entry pages.")

    return {
        "name": "day29-phase1-hardening",
        "paths": {
            "root": str(root),
            "docs_page": str(page.relative_to(root)) if page.exists() else docs_page_path,
            "report_page": str(report.relative_to(root))
            if report.exists()
            else "docs/day-29-ultra-upgrade-report.md",
        },
        "checks": checks,
        "summary": {
            "activation_score": score,
            "passed_checks": len(checks) - len(failed),
            "failed_checks": len(failed),
            "critical_failures": critical_failures,
            "strict_pass": not failed and not critical_failures,
        },
        "stale_hits": stale_hits,
        "gaps": gaps,
        "wins": [f"{check['check_id']} passed" for check in checks if check["passed"]],
        "corrective_actions": [f"Fix check: {check}" for check in failed],
    }


def _to_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return (
        "Day 29 phase-1 hardening summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Day 29 phase-1 hardening summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## Gaps",
        *[f"- {g}" for g in payload["gaps"] or ["No gaps detected."]],
        "",
        "## Corrective actions",
        *[
            f"- [ ] {a}"
            for a in payload["corrective_actions"] or ["No corrective actions required."]
        ],
    ]
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _emit_pack(root: Path, payload: dict[str, Any], pack_dir: Path) -> None:
    target = (root / pack_dir).resolve() if not pack_dir.is_absolute() else pack_dir
    target.mkdir(parents=True, exist_ok=True)
    _write(target / "day29-phase1-hardening-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day29-phase1-hardening-summary.md", _to_markdown(payload))
    _write(target / "day29-stale-gaps.json", json.dumps(payload["stale_hits"], indent=2) + "\n")
    _write(
        target / "day29-validation-commands.md",
        "# Day 29 validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
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
        "name": "day29-phase1-hardening-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "day29-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 29 phase-1 hardening scorer.")
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
            _write(page, _DAY29_DEFAULT_PAGE)

    payload = build_day29_phase1_hardening_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day29-hardening-pack/evidence")
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
