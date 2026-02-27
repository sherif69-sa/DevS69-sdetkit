from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day65-weekly-review-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY64_SUMMARY_PATH = "docs/artifacts/day64-integration-expansion-closeout-pack/day64-integration-expansion-closeout-summary.json"
_DAY64_BOARD_PATH = "docs/artifacts/day64-integration-expansion-closeout-pack/day64-delivery-board.md"
_DAY64_WORKFLOW_PATH = ".github/workflows/day64-advanced-github-actions-reference.yml"
_SECTION_HEADER = "# Day 65 — Weekly review #9 closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 65 matters",
    "## Required inputs (Day 64)",
    "## Day 65 command lane",
    "## Weekly review contract",
    "## Weekly review quality checklist",
    "## Day 65 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day65-weekly-review-closeout --format json --strict",
    "python -m sdetkit day65-weekly-review-closeout --emit-pack-dir docs/artifacts/day65-weekly-review-closeout-pack --format json --strict",
    "python -m sdetkit day65-weekly-review-closeout --execute --evidence-dir docs/artifacts/day65-weekly-review-closeout-pack/evidence --format json --strict",
    "python scripts/check_day65_weekly_review_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day65-weekly-review-closeout --format json --strict",
    "python -m sdetkit day65-weekly-review-closeout --emit-pack-dir docs/artifacts/day65-weekly-review-closeout-pack --format json --strict",
    "python scripts/check_day65_weekly_review_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 65 weekly review scoring, risk triage, and handoff signoff.",
    "The Day 65 lane references Day 64 integration evidence, delivery board completion, and strict baseline continuity.",
    "Every Day 65 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 65 closeout records weekly KPI deltas, governance decisions, and Day 66 integration expansion priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes KPI baseline deltas, confidence band, and anomaly narrative",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures pass-rate trend, reliability incidents, contributor signal quality, and recovery owner",
    "- [ ] Artifact pack includes weekly brief, KPI dashboard, decision register, risk ledger, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 65 weekly brief committed",
    "- [ ] Day 65 KPI dashboard snapshot exported",
    "- [ ] Day 65 governance decision register published",
    "- [ ] Day 65 risk and recovery ledger exported",
    "- [ ] Day 66 integration expansion priorities drafted from Day 65 review",
]

_DAY65_DEFAULT_PAGE = """# Day 65 — Weekly review #9 closeout lane

Day 65 closes with a major weekly review upgrade that converts Day 64 integration execution evidence into strict KPI governance and a deterministic Day 66 handoff.

## Why Day 65 matters

- Consolidates Day 64 integration expansion signals into a high-confidence weekly KPI baseline.
- Protects momentum with strict review contract coverage, runnable commands, and rollback safeguards.
- Creates a deterministic handoff from Day 65 weekly review into Day 66 integration expansion #2.

## Required inputs (Day 64)

- `docs/artifacts/day64-integration-expansion-closeout-pack/day64-integration-expansion-closeout-summary.json`
- `docs/artifacts/day64-integration-expansion-closeout-pack/day64-delivery-board.md`
- `.github/workflows/day64-advanced-github-actions-reference.yml`

## Day 65 command lane

```bash
python -m sdetkit day65-weekly-review-closeout --format json --strict
python -m sdetkit day65-weekly-review-closeout --emit-pack-dir docs/artifacts/day65-weekly-review-closeout-pack --format json --strict
python -m sdetkit day65-weekly-review-closeout --execute --evidence-dir docs/artifacts/day65-weekly-review-closeout-pack/evidence --format json --strict
python scripts/check_day65_weekly_review_closeout_contract.py
```

## Weekly review contract

- Single owner + backup reviewer are assigned for Day 65 weekly review scoring, risk triage, and handoff signoff.
- The Day 65 lane references Day 64 integration evidence, delivery board completion, and strict baseline continuity.
- Every Day 65 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 65 closeout records weekly KPI deltas, governance decisions, and Day 66 integration expansion priorities.

## Weekly review quality checklist

- [ ] Includes KPI baseline deltas, confidence band, and anomaly narrative
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures pass-rate trend, reliability incidents, contributor signal quality, and recovery owner
- [ ] Artifact pack includes weekly brief, KPI dashboard, decision register, risk ledger, and execution log

## Day 65 delivery board

- [ ] Day 65 weekly brief committed
- [ ] Day 65 KPI dashboard snapshot exported
- [ ] Day 65 governance decision register published
- [ ] Day 65 risk and recovery ledger exported
- [ ] Day 66 integration expansion priorities drafted from Day 65 review

## Scoring model

Day 65 weighted score (0-100):

- Contract + command lane completeness: 25 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 64 continuity and strict baseline carryover: 30 points.
- Weekly review quality + governance handoff: 25 points.
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


def _load_day64(path: Path) -> tuple[int, bool, int]:
    payload_obj = _load_json(path)
    if not isinstance(payload_obj, dict):
        return 0, False, 0
    summary_obj = payload_obj.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    score = int(summary.get("activation_score", 0))
    strict = bool(summary.get("strict_pass", False))
    checks_obj = payload_obj.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    return score, strict, len(checks)


def _count_board_items(path: Path, needle: str) -> tuple[int, bool]:
    text = _read(path)
    lines = [ln.strip() for ln in text.splitlines()]
    checks = [ln for ln in lines if ln.startswith("- [")]
    return len(checks), (needle in text)


def build_day65_weekly_review_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    day64_workflow_text = _read(root / _DAY64_WORKFLOW_PATH)

    day64_summary = root / _DAY64_SUMMARY_PATH
    day64_board = root / _DAY64_BOARD_PATH
    day64_score, day64_strict, day64_check_count = _load_day64(day64_summary)
    board_count, board_has_day64 = _count_board_items(day64_board, "Day 64")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day65_command",
            "weight": 7,
            "passed": ("day65-weekly-review-closeout" in readme_text),
            "evidence": "README day65 command lane",
        },
        {
            "check_id": "docs_index_day65_links",
            "weight": 8,
            "passed": (
                "day-65-big-upgrade-report.md" in docs_index_text
                and "integrations-day65-weekly-review-closeout.md" in docs_index_text
            ),
            "evidence": "day-65-big-upgrade-report.md + integrations-day65-weekly-review-closeout.md",
        },
        {
            "check_id": "top10_day65_alignment",
            "weight": 5,
            "passed": ("Day 65" in top10_text and "Day 66" in top10_text),
            "evidence": "Day 65 + Day 66 strategy chain",
        },
        {
            "check_id": "day64_summary_present",
            "weight": 10,
            "passed": day64_summary.exists(),
            "evidence": str(day64_summary),
        },
        {
            "check_id": "day64_delivery_board_present",
            "weight": 7,
            "passed": day64_board.exists(),
            "evidence": str(day64_board),
        },
        {
            "check_id": "day64_quality_floor",
            "weight": 13,
            "passed": day64_strict and day64_score >= 95,
            "evidence": {
                "day64_score": day64_score,
                "strict_pass": day64_strict,
                "day64_checks": day64_check_count,
            },
        },
        {
            "check_id": "day64_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day64,
            "evidence": {"board_items": board_count, "contains_day64": board_has_day64},
        },
        {
            "check_id": "page_header",
            "weight": 7,
            "passed": _SECTION_HEADER in page_text,
            "evidence": _SECTION_HEADER,
        },
        {
            "check_id": "required_sections",
            "weight": 8,
            "passed": not missing_sections,
            "evidence": missing_sections or "all sections present",
        },
        {
            "check_id": "required_commands",
            "weight": 5,
            "passed": not missing_commands,
            "evidence": missing_commands or "all commands present",
        },
        {
            "check_id": "contract_lock",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": missing_contract_lines or "contract locked",
        },
        {
            "check_id": "quality_checklist_lock",
            "weight": 5,
            "passed": not missing_quality_lines,
            "evidence": missing_quality_lines or "quality checklist locked",
        },
        {
            "check_id": "delivery_board_lock",
            "weight": 5,
            "passed": not missing_board_items,
            "evidence": missing_board_items or "delivery board locked",
        },
        {
            "check_id": "day64_workflow_reference_present",
            "weight": 10,
            "passed": "Day64 Advanced GitHub Actions Reference" in day64_workflow_text,
            "evidence": ".github/workflows/day64-advanced-github-actions-reference.yml",
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day64_summary.exists() or not day64_board.exists():
        critical_failures.append("day64_handoff_inputs")
    if not day64_strict:
        critical_failures.append("day64_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day64_strict:
        wins.append(f"Day 64 continuity is strict-pass with activation score={day64_score}.")
    else:
        misses.append("Day 64 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 64 closeout command and restore strict baseline before Day 65 lock."
        )

    if board_count >= 5 and board_has_day64:
        wins.append(
            f"Day 64 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 64 delivery board integrity is incomplete (needs >=5 items and Day 64 anchors)."
        )
        handoff_actions.append("Repair Day 64 delivery board entries to include Day 64 anchors.")

    if "Day64 Advanced GitHub Actions Reference" in day64_workflow_text:
        wins.append("Day 64 workflow reference remains available for weekly KPI baseline review.")
    else:
        misses.append("Day 64 workflow reference is missing for weekly review context.")
        handoff_actions.append("Restore day64 workflow reference before publishing Day 65 outcomes.")

    if not failed and not critical_failures:
        wins.append(
            "Day 65 weekly review closeout lane is fully complete and ready for Day 66 integration expansion #2."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day65-weekly-review-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day64_summary": str(day64_summary.relative_to(root)) if day64_summary.exists() else str(day64_summary),
            "day64_delivery_board": str(day64_board.relative_to(root)) if day64_board.exists() else str(day64_board),
            "day64_workflow": _DAY64_WORKFLOW_PATH,
        },
        "checks": checks,
        "rollup": {
            "day64_activation_score": day64_score,
            "day64_checks": day64_check_count,
            "day64_delivery_board_items": board_count,
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


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Day 65 weekly review closeout summary",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
    ]
    return "\n".join(lines)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _emit_pack(root: Path, pack_dir: Path, payload: dict[str, Any]) -> None:
    target = pack_dir if pack_dir.is_absolute() else root / pack_dir
    _write(
        target / "day65-weekly-review-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "day65-weekly-review-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day65-weekly-brief.md", "# Day 65 weekly brief\n")
    _write(target / "day65-kpi-dashboard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day65-governance-decision-register.md", "# Day 65 governance decision register\n")
    _write(target / "day65-risk-ledger.csv", "risk_id,severity,owner,mitigation,status\n")
    _write(target / "day65-execution-log.md", "# Day 65 execution log\n")
    _write(
        target / "day65-delivery-board.md",
        "\n".join(["# Day 65 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day65-validation-commands.md",
        "# Day 65 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    events: list[dict[str, Any]] = []
    out_dir = evidence_dir if evidence_dir.is_absolute() else root / evidence_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, command in enumerate(_EXECUTION_COMMANDS, start=1):
        result = subprocess.run(shlex.split(command), cwd=root, capture_output=True, text=True)
        event = {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        events.append(event)
        _write(out_dir / f"command-{idx:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        out_dir / "day65-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 65 weekly review closeout checks")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--write-default-doc", action="store_true")
    ns = parser.parse_args(argv)

    root = Path(ns.root).resolve()
    if ns.write_default_doc:
        _write(root / _PAGE_PATH, _DAY65_DEFAULT_PAGE)

    payload = build_day65_weekly_review_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day65-weekly-review-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
