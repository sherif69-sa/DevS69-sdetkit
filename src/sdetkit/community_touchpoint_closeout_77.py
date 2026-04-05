from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-community-touchpoint-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY76_SUMMARY_PATH = "docs/artifacts/contributor-recognition-closeout-pack/contributor-recognition-closeout-summary.json"
_DAY76_BOARD_PATH = (
    "docs/artifacts/contributor-recognition-closeout-pack/contributor-recognition-delivery-board.md"
)
_PLAN_PATH = "docs/roadmap/plans/community-touchpoint-plan.json"
_SECTION_HEADER = "# Community touchpoint closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 77 matters",
    "## Required inputs (Day 76)",
    "## Community touchpoint command lane",
    "## Community touchpoint contract",
    "## Touchpoint quality checklist",
    "## Community touchpoint delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit community-touchpoint-closeout --format json --strict",
    "python -m sdetkit community-touchpoint-closeout --emit-pack-dir docs/artifacts/community-touchpoint-closeout-pack --format json --strict",
    "python -m sdetkit community-touchpoint-closeout --execute --evidence-dir docs/artifacts/community-touchpoint-closeout-pack/evidence --format json --strict",
    "python scripts/check_community_touchpoint_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit community-touchpoint-closeout --format json --strict",
    "python -m sdetkit community-touchpoint-closeout --emit-pack-dir docs/artifacts/community-touchpoint-closeout-pack --format json --strict",
    "python scripts/check_community_touchpoint_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 77 community touchpoint execution and signoff.",
    "The Day 77 lane references Day 76 outcomes, controls, and KPI continuity signals.",
    "Every Day 77 section includes community CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 77 closeout records touchpoint outcomes, confidence notes, and Day 78 ecosystem priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes community baseline, touchpoint cadence, and stakeholder assumptions",
    "- [ ] Every touchpoint lane row has owner, session window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures touchpoint score delta, trust carryover delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, touchpoint plan, session ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 77 integration brief committed",
    "- [ ] Day 77 community touchpoint plan committed",
    "- [ ] Day 77 touchpoint session ledger exported",
    "- [ ] Day 77 touchpoint KPI scorecard snapshot exported",
    "- [ ] Day 78 ecosystem priorities drafted from Day 77 learnings",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"touchpoint_tracks"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DEFAULT_PAGE_TEMPLATE = """# Community touchpoint closeout lane

Day 77 closes with a major upgrade that converts Day 76 contributor-recognition outcomes into a community-touchpoint execution pack.

## Why Day 77 matters

- Turns Day 76 contributor-recognition outcomes into community-facing touchpoint proof across docs, governance, and release channels.
- Protects launch quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.
- Creates a deterministic handoff from Day 77 community touchpoint into Day 78 ecosystem priorities.

## Required inputs (Day 76)

- `docs/artifacts/contributor-recognition-closeout-pack/contributor-recognition-closeout-summary.json`
- `docs/artifacts/contributor-recognition-closeout-pack/contributor-recognition-delivery-board.md`
- `docs/roadmap/plans/community-touchpoint-plan.json`

## Community touchpoint command lane

```bash
python -m sdetkit community-touchpoint-closeout --format json --strict
python -m sdetkit community-touchpoint-closeout --emit-pack-dir docs/artifacts/community-touchpoint-closeout-pack --format json --strict
python -m sdetkit community-touchpoint-closeout --execute --evidence-dir docs/artifacts/community-touchpoint-closeout-pack/evidence --format json --strict
python scripts/check_community_touchpoint_closeout_contract.py
```

## Community touchpoint contract

- Single owner + backup reviewer are assigned for Day 77 community touchpoint execution and signoff.
- The Day 77 lane references Day 76 outcomes, controls, and KPI continuity signals.
- Every Day 77 section includes community CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 77 closeout records touchpoint outcomes, confidence notes, and Day 78 ecosystem priorities.

## Touchpoint quality checklist

- [ ] Includes community baseline, touchpoint cadence, and stakeholder assumptions
- [ ] Every touchpoint lane row has owner, session window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures touchpoint score delta, trust carryover delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, touchpoint plan, session ledger, KPI scorecard, and execution log

## Community touchpoint delivery board

- [ ] Day 77 integration brief committed
- [ ] Day 77 community touchpoint plan committed
- [ ] Day 77 touchpoint session ledger exported
- [ ] Day 77 touchpoint KPI scorecard snapshot exported
- [ ] Day 78 ecosystem priorities drafted from Day 77 learnings

## Scoring model

Day 77 weighted score (0-100):

- Contract + command lane integrity (35)
- Day 76 continuity baseline quality (35)
- Touchpoint evidence data + delivery board completeness (30)

Strict pass requires score >= 95 and zero critical failures.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_contributor_recognition(summary_path: Path) -> tuple[int, bool, int]:
    if not summary_path.exists():
        return 0, False, 0
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    checks = data.get("checks", [])
    return (
        int(summary.get("activation_score", 0)),
        bool(summary.get("strict_pass", False)),
        len(checks),
    )


def _count_board_items(board_path: Path, anchor: str) -> tuple[int, bool]:
    if not board_path.exists():
        return 0, False
    text = board_path.read_text(encoding="utf-8")
    items = [line for line in text.splitlines() if line.strip().startswith("- [")]
    return len(items), (anchor in text)


def build_community_touchpoint_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    plan_text = _read(root / _PLAN_PATH)

    contributor_recognition_summary = root / _DAY76_SUMMARY_PATH
    contributor_recognition_board = root / _DAY76_BOARD_PATH
    (
        contributor_recognition_score,
        contributor_recognition_strict,
        contributor_recognition_check_count,
    ) = _load_contributor_recognition(contributor_recognition_summary)
    board_count, board_has_contributor_recognition = _count_board_items(
        contributor_recognition_board, "Day 76"
    )

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_plan_keys = [x for x in _REQUIRED_DATA_KEYS if x not in plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_community_touchpoint_command",
            "weight": 7,
            "passed": ("community-touchpoint-closeout" in readme_text),
            "evidence": "README community-touchpoint command lane",
        },
        {
            "check_id": "docs_index_community_touchpoint_links",
            "weight": 8,
            "passed": (
                "impact-77-big-upgrade-report.md" in docs_index_text
                and "integrations-community-touchpoint-closeout.md" in docs_index_text
            ),
            "evidence": "impact-77-big-upgrade-report.md + integrations-community-touchpoint-closeout.md",
        },
        {
            "check_id": "top10_community_touchpoint_alignment",
            "weight": 5,
            "passed": (
                "Contributor recognition + community touchpoint strategy chain" in top10_text
            ),
            "evidence": "Contributor recognition + community touchpoint strategy chain",
        },
        {
            "check_id": "contributor_recognition_summary_present",
            "weight": 10,
            "passed": contributor_recognition_summary.exists(),
            "evidence": str(contributor_recognition_summary),
        },
        {
            "check_id": "contributor_recognition_delivery_board_present",
            "weight": 7,
            "passed": contributor_recognition_board.exists(),
            "evidence": str(contributor_recognition_board),
        },
        {
            "check_id": "contributor_recognition_quality_floor",
            "weight": 13,
            "passed": contributor_recognition_strict and contributor_recognition_score >= 95,
            "evidence": {
                "contributor_recognition_score": contributor_recognition_score,
                "strict_pass": contributor_recognition_strict,
                "contributor_recognition_checks": contributor_recognition_check_count,
            },
        },
        {
            "check_id": "contributor_recognition_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_contributor_recognition,
            "evidence": {
                "board_items": board_count,
                "contains_contributor_recognition": board_has_contributor_recognition,
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
            "check_id": "touchpoint_plan_data_present",
            "weight": 10,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not contributor_recognition_summary.exists() or not contributor_recognition_board.exists():
        critical_failures.append("contributor_recognition_handoff_inputs")
    if not contributor_recognition_strict:
        critical_failures.append("contributor_recognition_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if contributor_recognition_strict:
        wins.append(
            f"Day 76 continuity is strict-pass with activation score={contributor_recognition_score}."
        )
    else:
        misses.append("Day 76 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 76 closeout command and restore strict baseline before Day 77 lock."
        )

    if board_count >= 5 and board_has_contributor_recognition:
        wins.append(
            f"Day 76 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 76 delivery board integrity is incomplete (needs >=5 items and Day 76 anchors)."
        )
        handoff_actions.append("Repair Day 76 delivery board entries to include Day 76 anchors.")

    if not missing_plan_keys:
        wins.append("Day 77 community touchpoint dataset is available for launch execution.")
    else:
        misses.append("Day 77 community touchpoint dataset is missing required keys.")
        handoff_actions.append(
            "Update docs/roadmap/plans/community-touchpoint-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 77 community touchpoint closeout lane is fully complete and ready for Day 78 ecosystem priorities."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "community-touchpoint-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "contributor_recognition_summary": str(
                contributor_recognition_summary.relative_to(root)
            )
            if contributor_recognition_summary.exists()
            else str(contributor_recognition_summary),
            "contributor_recognition_delivery_board": str(
                contributor_recognition_board.relative_to(root)
            )
            if contributor_recognition_board.exists()
            else str(contributor_recognition_board),
            "touchpoint_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "contributor_recognition_activation_score": contributor_recognition_score,
            "contributor_recognition_checks": contributor_recognition_check_count,
            "contributor_recognition_delivery_board_items": board_count,
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
        "Community Touchpoint Closeout summary",
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
        target / "community-touchpoint-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "community-touchpoint-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "community-touchpoint-integration-brief.md",
        "# Community touchpoint integration brief\n",
    )
    _write(target / "community-touchpoint-plan.md", "# Community touchpoint plan\n")
    _write(
        target / "community-touchpoint-session-ledger.json",
        json.dumps({"sessions": []}, indent=2) + "\n",
    )
    _write(
        target / "community-touchpoint-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(
        target / "community-touchpoint-execution-log.md", "# Community touchpoint execution log\n"
    )
    _write(
        target / "community-touchpoint-delivery-board.md",
        "\n".join(["# Community touchpoint delivery board", *_REQUIRED_DELIVERY_BOARD_LINES])
        + "\n",
    )
    _write(
        target / "community-touchpoint-validation-commands.md",
        "# Community touchpoint validation commands\n\n```bash\n"
        + "\n".join(_EXECUTION_COMMANDS)
        + "\n```\n",
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
        out_dir / "community-touchpoint-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_community_touchpoint_closeout_summary_impl(root: Path) -> dict[str, Any]:
    """Compatibility alias for legacy day-based builder name."""
    return build_community_touchpoint_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Community Touchpoint Closeout checks")
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

    payload = build_community_touchpoint_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/community-touchpoint-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
