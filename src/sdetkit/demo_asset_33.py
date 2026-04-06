from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-demo-asset.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY32_SUMMARY_PATH = "docs/artifacts/release-cadence-pack/release-cadence-summary.json"
_DAY32_BOARD_PATH = "docs/artifacts/release-cadence-pack/release-delivery-board.md"
_SECTION_HEADER = "# \u2014 Demo asset #1 production"
_REQUIRED_SECTIONS = [
    "## Why matters",
    "## Required inputs ()",
    "## command lane",
    "## Demo production contract",
    "## Demo quality checklist",
    "## delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit demo-asset --format json --strict",
    "python -m sdetkit demo-asset --emit-pack-dir docs/artifacts/demo-asset-pack --format json --strict",
    "python -m sdetkit demo-asset --execute --evidence-dir docs/artifacts/demo-asset-pack/evidence --format json --strict",
    "python scripts/check_demo_asset_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit demo-asset --format json --strict",
    "python -m sdetkit demo-asset --emit-pack-dir docs/artifacts/demo-asset-pack --format json --strict",
    "python scripts/check_demo_asset_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Demo owner: one accountable editor and one backup reviewer are assigned.",
    "Target format: publish both MP4 clip and GIF teaser for social/docs embedding.",
    "Runtime SLA: main demo duration stays between 45 and 90 seconds.",
    "Narrative shape: pain -> command -> output -> value CTA must appear in order.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Shows `python -m sdetkit doctor --json` execution with readable terminal output",
    "- [ ] Includes before/after or problem/solution framing in first 10 seconds",
    "- [ ] Mentions one measurable trust signal (time saved, failures prevented, or coverage)",
    "- [ ] Includes docs link and CLI command in caption or description",
    "- [ ] Raw source file and final export are both stored in artifact pack",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] script draft committed",
    "- [ ] first cut rendered",
    "- [ ] final cut + caption copy approved",
    "- [ ] demo asset #2 backlog pre-scoped",
    "- [ ] KPI instrumentation plan updated",
]

_DEFAULT_PAGE_TEMPLATE = """# \u2014 Demo asset #1 production

closes the first demo-asset production lane so strategy turns into distributable proof.

## Why matters

- Converts release readiness into visible, shareable product storytelling.
- Creates a repeatable demo workflow for future release and community campaigns.
- Adds evidence discipline so every demo links back to runnable commands and docs.

## Required inputs ()

- `docs/artifacts/release-cadence-pack/release-cadence-summary.json`
- `docs/artifacts/release-cadence-pack/release-delivery-board.md`

## command lane

```bash
python -m sdetkit demo-asset --format json --strict
python -m sdetkit demo-asset --emit-pack-dir docs/artifacts/demo-asset-pack --format json --strict
python -m sdetkit demo-asset --execute --evidence-dir docs/artifacts/demo-asset-pack/evidence --format json --strict
python scripts/check_demo_asset_contract.py
```

## Demo production contract

- Demo owner: one accountable editor and one backup reviewer are assigned.
- Target format: publish both MP4 clip and GIF teaser for social/docs embedding.
- Runtime SLA: main demo duration stays between 45 and 90 seconds.
- Narrative shape: pain -> command -> output -> value CTA must appear in order.

## Demo quality checklist

- [ ] Shows `python -m sdetkit doctor --json` execution with readable terminal output
- [ ] Includes before/after or problem/solution framing in first 10 seconds
- [ ] Mentions one measurable trust signal (time saved, failures prevented, or coverage)
- [ ] Includes docs link and CLI command in caption or description
- [ ] Raw source file and final export are both stored in artifact pack

## delivery board

- [ ] script draft committed
- [ ] first cut rendered
- [ ] final cut + caption copy approved
- [ ] demo asset #2 backlog pre-scoped
- [ ] KPI instrumentation plan updated

## Scoring model

weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Release-cadence continuity and strict baseline carryover: 35 points.
- Demo contract lock + delivery board readiness: 15 points.
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


def _load_release_cadence_summary(path: Path) -> tuple[float, bool, int]:
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
    has_demo_asset_cycle33 = any(
        any(token in line for token in ("impact 33", "", "name 33")) for line in lines
    )
    has_demo_asset_cycle34 = any(
        any(token in line for token in ("impact 34", "", "name 34")) for line in lines
    )
    return item_count, has_demo_asset_cycle33, has_demo_asset_cycle34


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_demo_asset_summary_impl(
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

    release_cadence_summary_primary = root / _DAY32_SUMMARY_PATH
    release_cadence_board_primary = root / _DAY32_BOARD_PATH
    release_cadence_summary = release_cadence_summary_primary
    release_cadence_board = release_cadence_board_primary
    release_cadence_score, release_cadence_strict, release_cadence_check_count = (
        _load_release_cadence_summary(release_cadence_summary)
    )
    board_count, board_has_demo_asset_cycle33, board_has_demo_asset_cycle34 = _board_stats(
        release_cadence_board
    )

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
            "check_id": "readme_demo_asset_link",
            "weight": 8,
            "passed": "docs/integrations-demo-asset.md" in readme_text,
            "evidence": "docs/integrations-demo-asset.md",
        },
        {
            "check_id": "readme_demo_asset_command",
            "weight": 4,
            "passed": "demo-asset" in readme_text,
            "evidence": "demo-asset",
        },
        {
            "check_id": "docs_index_demo_asset_links",
            "weight": 8,
            "passed": (
                "impact-33-ultra-upgrade-report.md" in docs_index_text
                and "integrations-demo-asset.md" in docs_index_text
            ),
            "evidence": "impact-33-ultra-upgrade-report.md + integrations-demo-asset.md",
        },
        {
            "check_id": "top10_demo_asset_alignment",
            "weight": 5,
            "passed": (
                "\u2014 Demo asset #1" in top10_text
                and "\u2014 Demo asset #2" in top10_text
            ),
            "evidence": "+ strategy chain",
        },
        {
            "check_id": "release_cadence_summary_present",
            "weight": 10,
            "passed": release_cadence_summary.exists(),
            "evidence": {
                "resolved": str(release_cadence_summary),
                "primary": str(release_cadence_summary_primary),
            },
        },
        {
            "check_id": "release_cadence_delivery_board_present",
            "weight": 8,
            "passed": release_cadence_board.exists(),
            "evidence": {
                "resolved": str(release_cadence_board),
                "primary": str(release_cadence_board_primary),
            },
        },
        {
            "check_id": "release_cadence_quality_floor",
            "weight": 10,
            "passed": release_cadence_strict and release_cadence_score >= 95,
            "evidence": {
                "release_cadence_score": release_cadence_score,
                "strict_pass": release_cadence_strict,
                "release_cadence_checks": release_cadence_check_count,
            },
        },
        {
            "check_id": "release_cadence_board_integrity",
            "weight": 7,
            "passed": board_count >= 5
            and board_has_demo_asset_cycle33
            and board_has_demo_asset_cycle34,
            "evidence": {
                "board_items": board_count,
                "contains_previous": board_has_demo_asset_cycle33,
                "contains_current": board_has_demo_asset_cycle34,
            },
        },
        {
            "check_id": "demo_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "demo_quality_checklist_locked",
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
    if not release_cadence_summary.exists() or not release_cadence_board.exists():
        critical_failures.append("release_cadence_handoff_inputs")
    if not release_cadence_strict:
        critical_failures.append("release_cadence_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if release_cadence_strict:
        wins.append(
            f"Release-cadence continuity is strict-pass with activation score={release_cadence_score}."
        )
    else:
        misses.append("strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run cadence command and restore strict pass baseline before demo lock."
        )

    if board_count >= 5 and board_has_demo_asset_cycle33 and board_has_demo_asset_cycle34:
        wins.append(
            f"delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "delivery board integrity is incomplete (needs >=5 items and /34 anchors)."
        )
        handoff_actions.append(
            "Repair delivery board entries to include and anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Demo production contract + quality checklist is fully locked for execution.")
    else:
        misses.append("Demo contract, quality checklist, or delivery board entries are missing.")
        handoff_actions.append(
            "Complete all contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "demo asset #1 production is fully closed and ready for sequencing."
        )

    return {
        "name": "demo-asset",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "release_cadence_summary": str(release_cadence_summary.relative_to(root))
            if release_cadence_summary.exists()
            else str(release_cadence_summary),
            "release_cadence_delivery_board": str(release_cadence_board.relative_to(root))
            if release_cadence_board.exists()
            else str(release_cadence_board),
        },
        "checks": checks,
        "rollup": {
            "release_cadence_activation_score": release_cadence_score,
            "release_cadence_checks": release_cadence_check_count,
            "release_cadence_delivery_board_items": board_count,
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
        "demo asset summary\n"
        f"Activation score: {summary['activation_score']}\n"
        f"Passed checks: {summary['passed_checks']}\n"
        f"Failed checks: {summary['failed_checks']}\n"
        f"Critical failures: {', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}\n"
    )


def _to_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# demo asset summary",
        "",
        f"- Activation score: **{summary['activation_score']}**",
        f"- Passed checks: **{summary['passed_checks']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) if summary['critical_failures'] else 'none'}**",
        "",
        "## Release-cadence continuity",
        "",
        f"- activation score: `{payload['rollup']['release_cadence_activation_score']}`",
        f"- checks evaluated: `{payload['rollup']['release_cadence_checks']}`",
        f"- delivery board checklist items: `{payload['rollup']['release_cadence_delivery_board_items']}`",
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
    _write(target / "demo-asset-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "demo-asset-summary.md", _to_markdown(payload))
    _write(
        target / "demo-asset-plan.json",
        json.dumps(
            {
                "impact": 33,
                "asset": {
                    "id": "demo-asset-1",
                    "theme": "doctor workflow",
                    "primary_formats": ["mp4", "gif"],
                },
                "constraints": {"duration_seconds": {"min": 45, "max": 90}, "quality_floor": 95},
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "demo-script.md",
        "# demo script\n\n"
        "## Hook (0-10s)\n- Pain point + why this matters now\n\n"
        "## Command lane (10-45s)\n- Run: `python -m sdetkit doctor --json`\n- Highlight key output fields\n\n"
        "## Value proof + CTA (45-90s)\n- Trust signal + docs link + next step\n",
    )
    _write(
        target / "demo-delivery-board.md",
        "# delivery board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "demo-validation-commands.md",
        "# validation commands\n\n```bash\n" + "\n".join(_REQUIRED_COMMANDS) + "\n```\n",
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
        "name": "demo-asset-execution",
        "total_commands": len(logs),
        "failed_commands": [log["command"] for log in logs if log["returncode"] != 0],
        "commands": logs,
    }
    _write(target / "demo-execution-summary.json", json.dumps(summary, indent=2) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="demo asset #1 production scorer.")
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

    payload = build_demo_asset_summary_impl(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        ev_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/demo-asset-pack/evidence")
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


def build_demo_asset_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
) -> dict[str, Any]:
    """Canonical summary builder (legacy name retained as compatibility alias)."""
    return build_demo_asset_summary_impl(
        root,
        readme_path=readme_path,
        docs_index_path=docs_index_path,
        docs_page_path=docs_page_path,
        top10_path=top10_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
