from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day64-integration-expansion-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY63_SUMMARY_PATH = "docs/artifacts/day63-onboarding-activation-closeout-pack/day63-onboarding-activation-closeout-summary.json"
_DAY63_BOARD_PATH = (
    "docs/artifacts/day63-onboarding-activation-closeout-pack/day63-delivery-board.md"
)
_WORKFLOW_PATH = ".github/workflows/day64-advanced-github-actions-reference.yml"
_SECTION_HEADER = "# Day 64 — Integration expansion #1 closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 64 matters",
    "## Required inputs (Day 63)",
    "## Day 64 command lane",
    "## Integration expansion contract",
    "## Integration quality checklist",
    "## Day 64 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day64-integration-expansion-closeout --format json --strict",
    "python -m sdetkit day64-integration-expansion-closeout --emit-pack-dir docs/artifacts/day64-integration-expansion-closeout-pack --format json --strict",
    "python -m sdetkit day64-integration-expansion-closeout --execute --evidence-dir docs/artifacts/day64-integration-expansion-closeout-pack/evidence --format json --strict",
    "python scripts/check_day64_integration_expansion_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day64-integration-expansion-closeout --format json --strict",
    "python -m sdetkit day64-integration-expansion-closeout --emit-pack-dir docs/artifacts/day64-integration-expansion-closeout-pack --format json --strict",
    "python scripts/check_day64_integration_expansion_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 64 advanced GitHub Actions workflow execution and rollout signoff.",
    "The Day 64 lane references Day 63 onboarding outcomes, ownership handoff evidence, and KPI continuity signals.",
    "Every Day 64 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 64 closeout records reusable workflow design, matrix strategy, caching/concurrency controls, and Day 65 review priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes reusable workflow + workflow_call path, matrix coverage, and rollback trigger",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures workflow pass-rate, median runtime, cache hit-rate, confidence, and recovery owner",
    "- [ ] Artifact pack includes integration brief, workflow blueprint, matrix plan, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 64 integration brief committed",
    "- [ ] Day 64 advanced workflow blueprint published",
    "- [ ] Day 64 matrix and concurrency plan exported",
    "- [ ] Day 64 KPI scorecard snapshot exported",
    "- [ ] Day 65 weekly review priorities drafted from Day 64 learnings",
]
_REQUIRED_WORKFLOW_LINES = [
    "name: Day64 Advanced GitHub Actions Reference",
    "workflow_dispatch:",
    "workflow_call:",
    "strategy:",
    "matrix:",
    "concurrency:",
    "actions/cache@v4",
]

_DAY64_DEFAULT_PAGE = """# Day 64 — Integration expansion #1 closeout lane

Day 64 closes with a major integration upgrade that turns Day 63 onboarding momentum into an advanced GitHub Actions reference workflow with deterministic CI controls.

## Why Day 64 matters

- Converts Day 63 contributor activation into reusable CI automation patterns.
- Protects integration outcomes with strict contract coverage, runnable commands, and rollback safety.
- Creates a deterministic handoff from Day 64 integration expansion to Day 65 weekly review.

## Required inputs (Day 63)

- `docs/artifacts/day63-onboarding-activation-closeout-pack/day63-onboarding-activation-closeout-summary.json`
- `docs/artifacts/day63-onboarding-activation-closeout-pack/day63-delivery-board.md`

## Day 64 command lane

```bash
python -m sdetkit day64-integration-expansion-closeout --format json --strict
python -m sdetkit day64-integration-expansion-closeout --emit-pack-dir docs/artifacts/day64-integration-expansion-closeout-pack --format json --strict
python -m sdetkit day64-integration-expansion-closeout --execute --evidence-dir docs/artifacts/day64-integration-expansion-closeout-pack/evidence --format json --strict
python scripts/check_day64_integration_expansion_closeout_contract.py
```

## Integration expansion contract

- Single owner + backup reviewer are assigned for Day 64 advanced GitHub Actions workflow execution and rollout signoff.
- The Day 64 lane references Day 63 onboarding outcomes, ownership handoff evidence, and KPI continuity signals.
- Every Day 64 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 64 closeout records reusable workflow design, matrix strategy, caching/concurrency controls, and Day 65 review priorities.

## Integration quality checklist

- [ ] Includes reusable workflow + workflow_call path, matrix coverage, and rollback trigger
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures workflow pass-rate, median runtime, cache hit-rate, confidence, and recovery owner
- [ ] Artifact pack includes integration brief, workflow blueprint, matrix plan, KPI scorecard, and execution log

## Day 64 delivery board

- [ ] Day 64 integration brief committed
- [ ] Day 64 advanced workflow blueprint published
- [ ] Day 64 matrix and concurrency plan exported
- [ ] Day 64 KPI scorecard snapshot exported
- [ ] Day 65 weekly review priorities drafted from Day 64 learnings

## Scoring model

Day 64 weighted score (0-100):

- Contract + command lane completeness: 25 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 63 continuity and strict baseline carryover: 30 points.
- Workflow reference quality + guardrails: 25 points.
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


def _load_day63(path: Path) -> tuple[int, bool, int]:
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


def build_day64_integration_expansion_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    workflow_text = _read(root / _WORKFLOW_PATH)

    day63_summary = root / _DAY63_SUMMARY_PATH
    day63_board = root / _DAY63_BOARD_PATH
    day63_score, day63_strict, day63_check_count = _load_day63(day63_summary)
    board_count, board_has_day63 = _count_board_items(day63_board, "Day 63")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_workflow_lines = [x for x in _REQUIRED_WORKFLOW_LINES if x not in workflow_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day64_command",
            "weight": 7,
            "passed": ("day64-integration-expansion-closeout" in readme_text),
            "evidence": "README day64 command lane",
        },
        {
            "check_id": "docs_index_day64_links",
            "weight": 8,
            "passed": (
                "day-64-big-upgrade-report.md" in docs_index_text
                and "integrations-day64-integration-expansion-closeout.md" in docs_index_text
            ),
            "evidence": "day-64-big-upgrade-report.md + integrations-day64-integration-expansion-closeout.md",
        },
        {
            "check_id": "top10_day64_alignment",
            "weight": 5,
            "passed": ("Day 64" in top10_text and "Day 65" in top10_text),
            "evidence": "Day 64 + Day 65 strategy chain",
        },
        {
            "check_id": "day63_summary_present",
            "weight": 10,
            "passed": day63_summary.exists(),
            "evidence": str(day63_summary),
        },
        {
            "check_id": "day63_delivery_board_present",
            "weight": 7,
            "passed": day63_board.exists(),
            "evidence": str(day63_board),
        },
        {
            "check_id": "day63_quality_floor",
            "weight": 13,
            "passed": day63_strict and day63_score >= 95,
            "evidence": {
                "day63_score": day63_score,
                "strict_pass": day63_strict,
                "day63_checks": day63_check_count,
            },
        },
        {
            "check_id": "day63_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day63,
            "evidence": {"board_items": board_count, "contains_day63": board_has_day63},
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
            "check_id": "workflow_reference_lock",
            "weight": 10,
            "passed": not missing_workflow_lines,
            "evidence": missing_workflow_lines or "workflow locked",
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day63_summary.exists() or not day63_board.exists():
        critical_failures.append("day63_handoff_inputs")
    if not day63_strict:
        critical_failures.append("day63_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day63_strict:
        wins.append(f"Day 63 continuity is strict-pass with activation score={day63_score}.")
    else:
        misses.append("Day 63 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 63 closeout command and restore strict baseline before Day 64 lock."
        )

    if board_count >= 5 and board_has_day63:
        wins.append(
            f"Day 63 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 63 delivery board integrity is incomplete (needs >=5 items and Day 63 anchors)."
        )
        handoff_actions.append("Repair Day 63 delivery board entries to include Day 63 anchors.")

    if not missing_workflow_lines:
        wins.append("Advanced GitHub Actions workflow reference is fully locked for execution.")
    else:
        misses.append("Advanced workflow reference is missing required controls.")
        handoff_actions.append(
            "Complete workflow_dispatch/workflow_call/matrix/concurrency/cache lines in workflow file."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 64 integration expansion closeout lane is fully complete and ready for Day 65 weekly review."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day64-integration-expansion-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "workflow": _WORKFLOW_PATH,
            "day63_summary": str(day63_summary.relative_to(root))
            if day63_summary.exists()
            else str(day63_summary),
            "day63_delivery_board": str(day63_board.relative_to(root))
            if day63_board.exists()
            else str(day63_board),
        },
        "checks": checks,
        "rollup": {
            "day63_activation_score": day63_score,
            "day63_checks": day63_check_count,
            "day63_delivery_board_items": board_count,
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
        "Day 64 integration expansion closeout summary",
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
        target / "day64-integration-expansion-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "day64-integration-expansion-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day64-integration-brief.md", "# Day 64 integration brief\n")
    _write(target / "day64-workflow-blueprint.md", "# Day 64 workflow blueprint\n")
    _write(target / "day64-matrix-plan.csv", "os,python-version,owner\n")
    _write(target / "day64-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day64-execution-log.md", "# Day 64 execution log\n")
    _write(
        target / "day64-delivery-board.md",
        "\n".join(["# Day 64 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day64-validation-commands.md",
        "# Day 64 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day64-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 64 integration expansion closeout checks")
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
        _write(root / _PAGE_PATH, _DAY64_DEFAULT_PAGE)

    payload = build_day64_integration_expansion_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day64-integration-expansion-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
