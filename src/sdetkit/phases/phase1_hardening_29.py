from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-phase1-hardening.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_CANONICAL_LANE_NAME = "phase1-hardening"
_LEGACY_LANE_NAME = "legacy-phase1-hardening"
_CANONICAL_PACK_DIR = "docs/artifacts/phase1-hardening-pack"
_LEGACY_PACK_DIR = "docs/artifacts/legacy-phase1-hardening-pack"
_CANONICAL_SUMMARY_JSON = "phase1-hardening-summary.json"
_CANONICAL_SUMMARY_MD = "phase1-hardening-summary.md"
_CANONICAL_STALE_GAPS = "phase1-hardening-stale-gaps.json"
_CANONICAL_VALIDATION_COMMANDS = "phase1-hardening-validation-commands.md"
_CANONICAL_EXECUTION_SUMMARY = "phase1-hardening-execution-summary.json"
_SECTION_HEADER = "#  — Phase-1 hardening"
_REQUIRED_SECTIONS = [
    "## Why  exists",
    "## Hardening scope",
    "##  command lane",
    "## Scoring model",
    "## Entry page polish checklist",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit phase1-hardening --format json --strict",
    "python -m sdetkit phase1-hardening --emit-pack-dir docs/artifacts/phase1-hardening-pack --format json --strict",
    "python -m sdetkit phase1-hardening --execute --evidence-dir docs/artifacts/phase1-hardening-pack/evidence --format json --strict",
    "python scripts/check_phase1_hardening_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit phase1-hardening --format json --strict",
    "python scripts/check_phase1_hardening_contract.py --skip-evidence",
]
_STALE_MARKERS = ["TODO", "TBD", "lorem ipsum", "coming soon"]

_DEFAULT_PAGE_TEMPLATE = "#  — Phase-1 hardening\n\n closes Phase-1 by hardening top entry pages, removing stale guidance, and publishing a deterministic closeout lane.\n\n## Why  exists\n\n- Preserve trust by ensuring README + docs index + strategy pages are mutually consistent.\n- Close stale docs gaps before  phase wrap and handoff.\n- Produce a reviewable hardening artifact pack for maintainers.\n\n## Hardening scope\n\n- README entry-page checks and command-lane verification.\n- Docs index discoverability checks for  integration/report pages.\n- Strategy alignment checks against `docs/top-10-github-strategy.md`  objective.\n- Stale marker scans across top entry pages and recent integration docs.\n\n##  command lane\n\n```bash\npython -m sdetkit phase1-hardening --format json --strict\npython -m sdetkit phase1-hardening --emit-pack-dir docs/artifacts/phase1-hardening-pack --format json --strict\npython -m sdetkit phase1-hardening --execute --evidence-dir docs/artifacts/phase1-hardening-pack/evidence --format json --strict\npython scripts/check_phase1_hardening_contract.py\n```\n\n## Scoring model\n\n weighted score (0-100):\n\n- Docs contract and command-lane completeness: 35 points.\n- Entry-page discoverability + strategy alignment: 35 points.\n- Stale marker elimination in top pages: 20 points.\n- Artifact/report wiring for Phase-1 closeout: 10 points.\n\n## Entry page polish checklist\n\n- README includes  section and command lane.\n- Docs index links both integration guide and  report.\n- Top-10 strategy includes  hardening objective.\n- No stale placeholder markers in top entry pages.\n"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_phase1_hardening_summary_impl(
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
    report = root / "docs/impact-29-ultra-upgrade-report.md"

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
        "docs/integrations-phase1-hardening.md": page_text,
        "docs/integrations-weekly-review.md": _read(root / "docs/integrations-weekly-review.md"),
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
            "check_id": "readme_phase1_hardening_link",
            "weight": 12,
            "passed": "docs/integrations-phase1-hardening.md" in readme_text,
            "evidence": "docs/integrations-phase1-hardening.md",
        },
        {
            "check_id": "docs_index_phase1_hardening_links",
            "weight": 12,
            "passed": all(
                token in docs_index_text
                for token in [
                    "impact-29-ultra-upgrade-report.md",
                    "integrations-phase1-hardening.md",
                ]
            ),
            "evidence": "impact-29-ultra-upgrade-report.md + integrations-phase1-hardening.md",
        },
        {
            "check_id": "top10_phase1_hardening_alignment",
            "weight": 11,
            "passed": " — Phase-1 hardening" in top10_text,
            "evidence": " — Phase-1 hardening",
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
        gaps.append("Missing required  sections in integration page.")
    if missing_commands:
        gaps.append("Missing required command lane entries in integration page.")
    if stale_hits:
        gaps.append("Stale marker tokens detected across top entry pages.")

    return {
        "name": _CANONICAL_LANE_NAME,
        "legacy_name": _LEGACY_LANE_NAME,
        "paths": {
            "root": str(root),
            "docs_page": str(page.relative_to(root)) if page.exists() else docs_page_path,
            "report_page": str(report.relative_to(root))
            if report.exists()
            else "docs/impact-29-ultra-upgrade-report.md",
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
        " phase-1 hardening summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "#  phase-1 hardening summary",
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
    summary_json = json.dumps(payload, indent=2) + "\n"
    _write(target / _CANONICAL_SUMMARY_JSON, summary_json)
    summary_md = _to_markdown(payload)
    _write(target / _CANONICAL_SUMMARY_MD, summary_md)
    stale_json = json.dumps(payload["stale_hits"], indent=2) + "\n"
    _write(target / _CANONICAL_STALE_GAPS, stale_json)
    validation_md = (
        "#  validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n"
    )
    _write(target / _CANONICAL_VALIDATION_COMMANDS, validation_md)


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
        "name": "phase1-hardening-execution",
        "legacy_name": "legacy-phase1-hardening-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    execution_json = json.dumps(summary, indent=2) + "\n"
    _write(target / _CANONICAL_EXECUTION_SUMMARY, execution_json)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=" phase-1 hardening scorer.", epilog=" phase-1 hardening scorer"
    )
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
    if argv and "--help" in argv:
        print(" phase-1 hardening scorer")
    ns = parser.parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.write_defaults:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DEFAULT_PAGE_TEMPLATE)

    payload = build_phase1_hardening_summary_impl(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/phase1-hardening-pack/evidence")
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


def build_phase1_hardening_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
) -> dict[str, Any]:
    "Canonical summary builder (-based name retained as compatibility alias)."
    return build_phase1_hardening_summary_impl(
        root,
        readme_path=readme_path,
        docs_index_path=docs_index_path,
        docs_page_path=docs_page_path,
        top10_path=top10_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
