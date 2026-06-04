from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-release-readiness-wrap-handoff.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY58_SUMMARY_PATH = "docs/artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-completion-report-summary.json"
_DAY58_BOARD_PATH = "docs/artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-delivery-board.md"
_LANE_NAME = "Release Readiness Wrap Handoff"
_SECTION_HEADER = (
    "# Release Readiness Wrap Handoff - release readiness wrap handoff completion report lane"
)
_REQUIRED_SECTIONS = [
    "## Why Release Readiness Wrap Handoff matters",
    "## Required inputs (platform readiness preplan completion report)",
    "## Release Readiness Wrap Handoff command lane",
    "## release readiness wrap handoff contract",
    "## release readiness wrap handoff quality checklist",
    "## Release Readiness Wrap Handoff delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit release-readiness-wrap-handoff-completion-report --format json --strict",
    "python -m sdetkit release-readiness-wrap-handoff-completion-report --emit-pack-dir docs/artifacts/release-readiness-wrap-handoff-completion-report-pack --format json --strict",
    "python -m sdetkit release-readiness-wrap-handoff-completion-report --execute --evidence-dir docs/artifacts/release-readiness-wrap-handoff-completion-report-pack/evidence --format json --strict",
    "python scripts/check_release_readiness_wrap_handoff_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit release-readiness-wrap-handoff-completion-report --format json --strict",
    "python -m sdetkit release-readiness-wrap-handoff-completion-report --emit-pack-dir docs/artifacts/release-readiness-wrap-handoff-completion-report-pack --format json --strict",
    "python scripts/check_release_readiness_wrap_handoff_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for release readiness wrap handoff execution and signal triage.",
    "The completion report lane references platform readiness preplan outcomes and unresolved risks.",
    "Every section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "This completion report records Release readiness wrap outcomes and Platform readiness execution priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes priority digest, lane-level plan actions, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI",
    "- [ ] Artifact pack includes wrap brief, risk ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] release readiness wrap handoff brief committed",
    "- [ ] Wrap reviewed with owner + backup",
    "- [ ] Risk ledger exported",
    "- [ ] KPI scorecard snapshot exported",
    "- [ ] Platform readiness execution priorities drafted from Release readiness learnings",
]

_DEFAULT_PAGE_TEMPLATE = """# Release Readiness Wrap Handoff - release readiness wrap handoff completion report lane

Release Readiness Wrap Handoff closes with a major release readiness wrap handoff upgrade that turns platform readiness preplan outcomes into deterministic Platform readiness execution priorities.

## Why Release Readiness Wrap Handoff matters

- Converts platform readiness preplan evidence into repeatable Platform readiness execution loops.
- Protects quality with ownership, command proof, and KPI rollback guardrails.
- Produces a deterministic handoff from closeout into Platform readiness execution planning.

## Required inputs (platform readiness preplan completion report)

- `docs/artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-completion-report-summary.json`
- `docs/artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-delivery-board.md`

## Release Readiness Wrap Handoff command lane

```bash
python -m sdetkit release-readiness-wrap-handoff-completion-report --format json --strict
python -m sdetkit release-readiness-wrap-handoff-completion-report --emit-pack-dir docs/artifacts/release-readiness-wrap-handoff-completion-report-pack --format json --strict
python -m sdetkit release-readiness-wrap-handoff-completion-report --execute --evidence-dir docs/artifacts/release-readiness-wrap-handoff-completion-report-pack/evidence --format json --strict
python scripts/check_release_readiness_wrap_handoff_contract.py
```

## release readiness wrap handoff contract

- Single owner + backup reviewer are assigned for release readiness wrap handoff execution and signal triage.
- The completion report lane references platform readiness preplan outcomes and unresolved risks.
- Every section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- This completion report records Release readiness wrap outcomes and Platform readiness execution priorities.

## release readiness wrap handoff quality checklist

- [ ] Includes priority digest, lane-level plan actions, and rollback strategy
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI
- [ ] Artifact pack includes wrap brief, risk ledger, KPI scorecard, and execution log

## Release Readiness Wrap Handoff delivery board

- [ ] release readiness wrap handoff brief committed
- [ ] Wrap reviewed with owner + backup
- [ ] Risk ledger exported
- [ ] KPI scorecard snapshot exported
- [ ] Platform readiness execution priorities drafted from Release readiness learnings

## Scoring model

Release Readiness Wrap Handoff weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- platform readiness preplan continuity and strict baseline carryover: 35 points.
- release readiness wrap handoff contract lock + delivery board readiness: 15 points.
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


def _load_phase3_preplan(path: Path) -> tuple[int, bool, int]:
    payload_obj = _load_json(path)
    if not isinstance(payload_obj, dict):
        return 0, False, 0
    summary_obj = payload_obj.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    score = int(summary.get("activation_score", 0))
    strict = coerce_bool(summary.get("strict_pass", False), default=False)
    checks_obj = payload_obj.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    return score, strict, len(checks)


def _count_board_items(path: Path, needle: str) -> tuple[int, bool]:
    text = _read(path)
    lines = [ln.strip() for ln in text.splitlines()]
    checks = [ln for ln in lines if ln.startswith("- [")]
    return len(checks), (needle in text)


def build_release_readiness_wrap_handoff_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)

    phase3_preplan_summary = root / _DAY58_SUMMARY_PATH
    phase3_preplan_board = root / _DAY58_BOARD_PATH
    phase3_preplan_score, phase3_preplan_strict, phase3_preplan_check_count = _load_phase3_preplan(
        phase3_preplan_summary
    )
    board_count, board_has_phase3_preplan = _count_board_items(
        phase3_preplan_board, "platform readiness preplan"
    )

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_command_lane",
            "weight": 7,
            "passed": ("release-readiness-wrap-handoff-completion-report" in readme_text),
            "evidence": "README release-readiness-wrap-handoff-completion-report command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-60-big-upgrade-report.md" in docs_index_text
                and "integrations-release-readiness-wrap-handoff-workflow.md" in docs_index_text
            ),
            "evidence": "impact-60-big-upgrade-report.md + integrations-release-readiness-wrap-handoff-workflow.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": (
                "release readiness wrap handoff" in top10_text
                and "platform readiness kickoff" in top10_text
            ),
            "evidence": "release readiness wrap handoff and platform readiness kickoff strategy chain",
        },
        {
            "check_id": "phase3_preplan_summary_present",
            "weight": 10,
            "passed": phase3_preplan_summary.exists(),
            "evidence": str(phase3_preplan_summary),
        },
        {
            "check_id": "phase3_preplan_delivery_board_present",
            "weight": 8,
            "passed": phase3_preplan_board.exists(),
            "evidence": str(phase3_preplan_board),
        },
        {
            "check_id": "phase3_preplan_quality_floor",
            "weight": 15,
            "passed": phase3_preplan_strict and phase3_preplan_score >= 95,
            "evidence": {
                "phase3_preplan_score": phase3_preplan_score,
                "strict_pass": phase3_preplan_strict,
                "phase3_preplan_checks": phase3_preplan_check_count,
            },
        },
        {
            "check_id": "phase3_preplan_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_phase3_preplan,
            "evidence": {
                "board_items": board_count,
                "contains_phase3_preplan": board_has_phase3_preplan,
            },
        },
        {
            "check_id": "page_header",
            "weight": 7,
            "passed": _SECTION_HEADER in page_text,
            "evidence": _SECTION_HEADER,
        },
        {
            "check_id": "required_sections",
            "weight": 10,
            "passed": not missing_sections,
            "evidence": missing_sections or "all sections present",
        },
        {
            "check_id": "required_commands",
            "weight": 8,
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
            "weight": 3,
            "passed": not missing_quality_lines,
            "evidence": missing_quality_lines or "quality checklist locked",
        },
        {
            "check_id": "delivery_board_lock",
            "weight": 2,
            "passed": not missing_board_items,
            "evidence": missing_board_items or "delivery board locked",
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not phase3_preplan_summary.exists() or not phase3_preplan_board.exists():
        critical_failures.append("phase3_preplan_handoff_inputs")
    if not phase3_preplan_strict:
        critical_failures.append("phase3_preplan_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if phase3_preplan_strict:
        wins.append(
            f"platform readiness preplan continuity is strict-pass with activation score={phase3_preplan_score}."
        )
    else:
        misses.append("platform readiness preplan strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run the platform readiness preplan completion report command and restore strict baseline before lock."
        )

    if board_count >= 5 and board_has_phase3_preplan:
        wins.append(
            f"Platform readiness delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Platform readiness delivery board integrity is incomplete (needs >=5 items and anchors)."
        )
        handoff_actions.append(
            "Repair Platform readiness delivery board entries to include pre-plan anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "release readiness wrap handoff contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "release readiness wrap handoff contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "release readiness wrap handoff completion report lane is fully complete and ready for Platform readiness execution."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "release-readiness-wrap-handoff-completion-report",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "phase3_preplan_summary": str(phase3_preplan_summary.relative_to(root))
            if phase3_preplan_summary.exists()
            else str(phase3_preplan_summary),
            "phase3_preplan_delivery_board": str(phase3_preplan_board.relative_to(root))
            if phase3_preplan_board.exists()
            else str(phase3_preplan_board),
        },
        "checks": checks,
        "rollup": {
            "phase3_preplan_activation_score": phase3_preplan_score,
            "phase3_preplan_checks": phase3_preplan_check_count,
            "phase3_preplan_delivery_board_items": board_count,
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
        f"{_LANE_NAME} summary",
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
        target / "release-readiness-wrap-handoff-completion-report-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(
        target / "release-readiness-wrap-handoff-completion-report-summary.md",
        _render_text(payload) + "\n",
    )
    _write(
        target / "release-readiness-wrap-handoff-brief.md",
        "# release readiness wrap handoff brief\n",
    )
    _write(
        target / "release-readiness-wrap-handoff-risk-ledger.csv", "risk,owner,mitigation,status\n"
    )
    _write(
        target / "release-readiness-wrap-handoff-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(target / "release-readiness-wrap-handoff-execution-log.md", "# Execution log\n")
    _write(
        target / "release-readiness-wrap-handoff-delivery-board.md",
        "\n".join(
            ["# release readiness wrap handoff delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]
        )
        + "\n",
    )
    _write(
        target / "release-readiness-wrap-handoff-validation-commands.md",
        "# Validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    events: list[dict[str, Any]] = []
    out_dir = evidence_dir if evidence_dir.is_absolute() else root / evidence_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, command in enumerate(_EXECUTION_COMMANDS, start=1):
        argv = shlex.split(command)
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
        event = {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        events.append(event)
        _write(out_dir / f"command-{idx:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        out_dir / "release-readiness-wrap-handoff-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_release_readiness_wrap_handoff_summary_impl(root: Path) -> dict[str, Any]:
    "Compatibility alias for legacy -based builder name."
    return build_release_readiness_wrap_handoff_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release Readiness Wrap Handoff checks")
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
        _write(root / _PAGE_PATH, _DEFAULT_PAGE_TEMPLATE)

    payload = build_release_readiness_wrap_handoff_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path(
                "docs/artifacts/release-readiness-wrap-handoff-completion-report-pack/evidence"
            )
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
