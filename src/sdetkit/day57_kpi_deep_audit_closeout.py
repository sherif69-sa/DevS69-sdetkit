from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day57-kpi-deep-audit-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY56_SUMMARY_PATH = (
    "docs/artifacts/day56-stabilization-closeout-pack/day56-stabilization-closeout-summary.json"
)
_DAY56_BOARD_PATH = "docs/artifacts/day56-stabilization-closeout-pack/day56-delivery-board.md"
_SECTION_HEADER = "# Day 57 — KPI deep audit closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 57 matters",
    "## Required inputs (Day 56)",
    "## Day 57 command lane",
    "## KPI deep audit contract",
    "## KPI deep audit quality checklist",
    "## Day 57 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day57-kpi-deep-audit-closeout --format json --strict",
    "python -m sdetkit day57-kpi-deep-audit-closeout --emit-pack-dir docs/artifacts/day57-kpi-deep-audit-closeout-pack --format json --strict",
    "python -m sdetkit day57-kpi-deep-audit-closeout --execute --evidence-dir docs/artifacts/day57-kpi-deep-audit-closeout-pack/evidence --format json --strict",
    "python scripts/check_day57_kpi_deep_audit_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day57-kpi-deep-audit-closeout --format json --strict",
    "python -m sdetkit day57-kpi-deep-audit-closeout --emit-pack-dir docs/artifacts/day57-kpi-deep-audit-closeout-pack --format json --strict",
    "python scripts/check_day57_kpi_deep_audit_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 57 KPI deep-audit execution and signal triage.",
    "The Day 57 lane references Day 56 stabilization outcomes and unresolved risks.",
    "Every Day 57 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 57 closeout records deep-audit outcomes and Day 58 execution priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes KPI trendline digest, anomaly triage, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI",
    "- [ ] Artifact pack includes audit brief, risk ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 57 KPI deep audit brief committed",
    "- [ ] Day 57 deep-audit plan reviewed with owner + backup",
    "- [ ] Day 57 risk ledger exported",
    "- [ ] Day 57 KPI scorecard snapshot exported",
    "- [ ] Day 58 execution priorities drafted from Day 57 learnings",
]

_DAY57_DEFAULT_PAGE = """# Day 57 — KPI deep audit closeout lane

Day 57 closes with a major KPI deep-audit upgrade that turns Day 56 stabilization outcomes into deterministic trendline governance.

## Why Day 57 matters

- Converts Day 56 stabilization evidence into repeatable KPI anomaly triage loops.
- Protects quality with ownership, command proof, and KPI rollback guardrails.
- Produces a deterministic handoff from Day 57 closeout into Day 58 execution planning.

## Required inputs (Day 56)

- `docs/artifacts/day56-stabilization-closeout-pack/day56-stabilization-closeout-summary.json`
- `docs/artifacts/day56-stabilization-closeout-pack/day56-delivery-board.md`

## Day 57 command lane

```bash
python -m sdetkit day57-kpi-deep-audit-closeout --format json --strict
python -m sdetkit day57-kpi-deep-audit-closeout --emit-pack-dir docs/artifacts/day57-kpi-deep-audit-closeout-pack --format json --strict
python -m sdetkit day57-kpi-deep-audit-closeout --execute --evidence-dir docs/artifacts/day57-kpi-deep-audit-closeout-pack/evidence --format json --strict
python scripts/check_day57_kpi_deep_audit_closeout_contract.py
```

## KPI deep audit contract

- Single owner + backup reviewer are assigned for Day 57 KPI deep-audit execution and signal triage.
- The Day 57 lane references Day 56 stabilization outcomes and unresolved risks.
- Every Day 57 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 57 closeout records deep-audit outcomes and Day 58 execution priorities.

## KPI deep audit quality checklist

- [ ] Includes KPI trendline digest, anomaly triage, and rollback strategy
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI
- [ ] Artifact pack includes audit brief, risk ledger, KPI scorecard, and execution log

## Day 57 delivery board

- [ ] Day 57 KPI deep audit brief committed
- [ ] Day 57 deep-audit plan reviewed with owner + backup
- [ ] Day 57 risk ledger exported
- [ ] Day 57 KPI scorecard snapshot exported
- [ ] Day 58 execution priorities drafted from Day 57 learnings

## Scoring model

Day 57 weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 56 continuity and strict baseline carryover: 35 points.
- KPI deep-audit contract lock + delivery board readiness: 15 points.
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


def _load_day56(path: Path) -> tuple[int, bool, int]:
    payload = _load_json(path)
    if payload is None:
        return 0, False, 0
    summary_obj = payload.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    checks_obj = payload.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    score = int(summary.get("activation_score", 0) or 0)
    strict = bool(summary.get("strict_pass", False))
    return score, strict, len(checks)


def _load_board(path: Path) -> tuple[int, bool]:
    if not path.exists():
        return 0, False
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    items = [line for line in lines if line.startswith("- [")]
    has_day56 = any("Day 56" in line for line in lines)
    return len(items), has_day56


def build_day57_kpi_deep_audit_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_path = root / _PAGE_PATH
    page_text = _read(page_path)
    top10_text = _read(root / _TOP10_PATH)
    day56_summary = root / _DAY56_SUMMARY_PATH
    day56_board = root / _DAY56_BOARD_PATH

    day56_score, day56_strict, day56_check_count = _load_day56(day56_summary)
    board_count, board_has_day56 = _load_board(day56_board)

    missing_sections = [s for s in _REQUIRED_SECTIONS if s not in page_text]
    missing_commands = [c for c in _REQUIRED_COMMANDS if c not in page_text]
    missing_contract_lines = [line for line in _REQUIRED_CONTRACT_LINES if line not in page_text]
    missing_quality_lines = [line for line in _REQUIRED_QUALITY_LINES if line not in page_text]
    missing_board_items = [line for line in _REQUIRED_DELIVERY_BOARD_LINES if line not in page_text]

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
            "check_id": "readme_day57_link",
            "weight": 8,
            "passed": _PAGE_PATH in readme_text,
            "evidence": _PAGE_PATH,
        },
        {
            "check_id": "readme_day57_command",
            "weight": 4,
            "passed": "day57-kpi-deep-audit-closeout" in readme_text,
            "evidence": "day57-kpi-deep-audit-closeout",
        },
        {
            "check_id": "docs_index_day57_links",
            "weight": 8,
            "passed": (
                "day-57-big-upgrade-report.md" in docs_index_text
                and "integrations-day57-kpi-deep-audit-closeout.md" in docs_index_text
            ),
            "evidence": "day-57-big-upgrade-report.md + integrations-day57-kpi-deep-audit-closeout.md",
        },
        {
            "check_id": "top10_day57_alignment",
            "weight": 5,
            "passed": ("Day 57" in top10_text and "Day 58" in top10_text),
            "evidence": "Day 57 + Day 58 strategy chain",
        },
        {
            "check_id": "day56_summary_present",
            "weight": 10,
            "passed": day56_summary.exists(),
            "evidence": str(day56_summary),
        },
        {
            "check_id": "day56_delivery_board_present",
            "weight": 8,
            "passed": day56_board.exists(),
            "evidence": str(day56_board),
        },
        {
            "check_id": "day56_quality_floor",
            "weight": 10,
            "passed": day56_strict and day56_score >= 95,
            "evidence": {
                "day56_score": day56_score,
                "strict_pass": day56_strict,
                "day56_checks": day56_check_count,
            },
        },
        {
            "check_id": "day56_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day56,
            "evidence": {"board_items": board_count, "contains_day56": board_has_day56},
        },
        {
            "check_id": "kpi_deep_audit_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "kpi_deep_audit_quality_checklist_locked",
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
    critical_failures: list[str] = []
    if not day56_summary.exists() or not day56_board.exists():
        critical_failures.append("day56_handoff_inputs")
    if not day56_strict:
        critical_failures.append("day56_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day56_strict:
        wins.append(f"Day 56 continuity is strict-pass with activation score={day56_score}.")
    else:
        misses.append("Day 56 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 56 stabilization closeout command and restore strict baseline before Day 57 lock."
        )

    if board_count >= 5 and board_has_day56:
        wins.append(
            f"Day 56 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 56 delivery board integrity is incomplete (needs >=5 items and Day 56 anchors)."
        )
        handoff_actions.append("Repair Day 56 delivery board entries to include Day 56 anchors.")

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("KPI deep-audit contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "KPI deep-audit contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 57 contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 57 KPI deep-audit closeout lane is fully complete and ready for Day 58 execution lane."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day57-kpi-deep-audit-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day56_summary": str(day56_summary.relative_to(root))
            if day56_summary.exists()
            else str(day56_summary),
            "day56_delivery_board": str(day56_board.relative_to(root))
            if day56_board.exists()
            else str(day56_board),
        },
        "checks": checks,
        "rollup": {
            "day56_activation_score": day56_score,
            "day56_checks": day56_check_count,
            "day56_delivery_board_items": board_count,
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
        "Day 57 KPI deep-audit closeout summary",
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
        target / "day57-kpi-deep-audit-closeout-summary.json", json.dumps(payload, indent=2) + "\n"
    )
    _write(target / "day57-kpi-deep-audit-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day57-kpi-deep-audit-brief.md", "# Day 57 KPI deep-audit brief\n")
    _write(target / "day57-risk-ledger.csv", "risk,owner,mitigation,status\n")
    _write(target / "day57-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day57-execution-log.md", "# Day 57 execution log\n")
    _write(
        target / "day57-delivery-board.md",
        "\n".join(["# Day 57 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day57-validation-commands.md",
        "# Day 57 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day57-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 57 KPI deep audit closeout checks")
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
        _write(root / _PAGE_PATH, _DAY57_DEFAULT_PAGE)

    payload = build_day57_kpi_deep_audit_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day57-kpi-deep-audit-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
