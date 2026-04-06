from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-weekly-review-closeout-2.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_INTEGRATION_EXPANSION_SUMMARY_PATH = (
    "docs/artifacts/integration-expansion-closeout-pack/integration-expansion-closeout-summary.json"
)
_INTEGRATION_EXPANSION_BOARD_PATH = (
    "docs/artifacts/integration-expansion-closeout-pack/integration-expansion-delivery-board.md"
)
_INTEGRATION_EXPANSION_WORKFLOW_PATH = ".github/workflows/advanced-github-actions-reference-64.yml"
_SECTION_HEADER = "#  — Weekly review #9 closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Weekly Review Closeout matters",
    "## Required inputs ()",
    "## Weekly Review Closeout command lane",
    "## Weekly review contract",
    "## Weekly review quality checklist",
    "## Weekly Review Closeout delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit weekly-review-closeout --format json --strict",
    "python -m sdetkit weekly-review-closeout --emit-pack-dir docs/artifacts/weekly-review-closeout-2-pack --format json --strict",
    "python -m sdetkit weekly-review-closeout --execute --evidence-dir docs/artifacts/weekly-review-closeout-2-pack/evidence --format json --strict",
    "python scripts/check_weekly_review_closeout_contract_2.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit weekly-review-closeout --format json --strict",
    "python -m sdetkit weekly-review-closeout --emit-pack-dir docs/artifacts/weekly-review-closeout-2-pack --format json --strict",
    "python scripts/check_weekly_review_closeout_contract_2.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for  weekly review scoring, risk triage, and handoff signoff.",
    "The  lane references  integration evidence, delivery board completion, and strict baseline continuity.",
    "Every  section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    " closeout records weekly KPI deltas, governance decisions, and  integration expansion priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes KPI baseline deltas, confidence band, and anomaly narrative",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures pass-rate trend, reliability incidents, contributor signal quality, and recovery owner",
    "- [ ] Artifact pack includes weekly brief, KPI dashboard, decision register, risk ledger, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ]  weekly brief committed",
    "- [ ]  KPI dashboard snapshot exported",
    "- [ ]  governance decision register published",
    "- [ ]  risk and recovery ledger exported",
    "- [ ]  integration expansion priorities drafted from  review",
]

_DEFAULT_PAGE_TEMPLATE = "#  — Weekly review #9 closeout lane\n\n closes with a major weekly review upgrade that converts  integration execution evidence into strict KPI governance and a deterministic  handoff.\n\n## Why Weekly Review Closeout matters\n\n- Consolidates  integration expansion signals into a high-confidence weekly KPI baseline.\n- Protects momentum with strict review contract coverage, runnable commands, and rollback safeguards.\n- Creates a deterministic handoff from  weekly review into  integration expansion #2.\n\n## Required inputs ()\n\n- `docs/artifacts/integration-expansion-closeout-pack/integration-expansion-closeout-summary.json`\n- `docs/artifacts/integration-expansion-closeout-pack/integration-expansion-delivery-board.md`\n- `.github/workflows/advanced-github-actions-reference-64.yml`\n\n## Weekly Review Closeout command lane\n\n```bash\npython -m sdetkit weekly-review-closeout --format json --strict\npython -m sdetkit weekly-review-closeout --emit-pack-dir docs/artifacts/weekly-review-closeout-2-pack --format json --strict\npython -m sdetkit weekly-review-closeout --execute --evidence-dir docs/artifacts/weekly-review-closeout-2-pack/evidence --format json --strict\npython scripts/check_weekly_review_closeout_contract_2.py\n```\n\n## Weekly review contract\n\n- Single owner + backup reviewer are assigned for  weekly review scoring, risk triage, and handoff signoff.\n- The  lane references  integration evidence, delivery board completion, and strict baseline continuity.\n- Every  section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n-  closeout records weekly KPI deltas, governance decisions, and  integration expansion priorities.\n\n## Weekly review quality checklist\n\n- [ ] Includes KPI baseline deltas, confidence band, and anomaly narrative\n- [ ] Every section has owner, review window, KPI threshold, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures pass-rate trend, reliability incidents, contributor signal quality, and recovery owner\n- [ ] Artifact pack includes weekly brief, KPI dashboard, decision register, risk ledger, and execution log\n\n## Weekly Review Closeout delivery board\n\n- [ ]  weekly brief committed\n- [ ]  KPI dashboard snapshot exported\n- [ ]  governance decision register published\n- [ ]  risk and recovery ledger exported\n- [ ]  integration expansion priorities drafted from  review\n\n## Scoring model\n\n weighted score (0-100):\n\n- Contract + command lane completeness: 25 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 30 points.\n- Weekly review quality + governance handoff: 25 points.\n"


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


def _load_integration_expansion(path: Path) -> tuple[int, bool, int]:
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


def build_weekly_review_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    integration_expansion_workflow_text = _read(root / _INTEGRATION_EXPANSION_WORKFLOW_PATH)

    integration_expansion_summary = root / _INTEGRATION_EXPANSION_SUMMARY_PATH
    integration_expansion_board = root / _INTEGRATION_EXPANSION_BOARD_PATH
    integration_expansion_score, integration_expansion_strict, integration_expansion_check_count = (
        _load_integration_expansion(integration_expansion_summary)
    )
    board_count, board_has_integration_expansion = _count_board_items(
        integration_expansion_board, ""
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
            "passed": ("weekly-review-closeout-2" in readme_text),
            "evidence": "README weekly-review-closeout-2 command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-65-big-upgrade-report.md" in docs_index_text
                and "integrations-weekly-review-closeout-2.md" in docs_index_text
            ),
            "evidence": "impact-65-big-upgrade-report.md + integrations-weekly-review-closeout-2.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ("" in top10_text and "" in top10_text),
            "evidence": " +  strategy chain",
        },
        {
            "check_id": "integration_expansion_summary_present",
            "weight": 10,
            "passed": integration_expansion_summary.exists(),
            "evidence": str(integration_expansion_summary),
        },
        {
            "check_id": "integration_expansion_delivery_board_present",
            "weight": 7,
            "passed": integration_expansion_board.exists(),
            "evidence": str(integration_expansion_board),
        },
        {
            "check_id": "integration_expansion_quality_floor",
            "weight": 13,
            "passed": integration_expansion_strict and integration_expansion_score >= 95,
            "evidence": {
                "integration_expansion_score": integration_expansion_score,
                "strict_pass": integration_expansion_strict,
                "integration_expansion_checks": integration_expansion_check_count,
            },
        },
        {
            "check_id": "integration_expansion_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_integration_expansion,
            "evidence": {
                "board_items": board_count,
                "contains_integration_expansion": board_has_integration_expansion,
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
            "check_id": "integration_expansion_workflow_reference_present",
            "weight": 10,
            "passed": " Advanced GitHub Actions Reference" in integration_expansion_workflow_text,
            "evidence": ".github/workflows/advanced-github-actions-reference-64.yml",
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not integration_expansion_summary.exists() or not integration_expansion_board.exists():
        critical_failures.append("integration_expansion_handoff_inputs")
    if not integration_expansion_strict:
        critical_failures.append("integration_expansion_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if integration_expansion_strict:
        wins.append(
            f"64 continuity is strict-pass with activation score={integration_expansion_score}."
        )
    else:
        misses.append(" strict continuity signal is missing.")
        handoff_actions.append("Re-run  closeout command and restore strict baseline before  lock.")

    if board_count >= 5 and board_has_integration_expansion:
        wins.append(f"64 delivery board integrity validated with {board_count} checklist items.")
    else:
        misses.append(" delivery board integrity is incomplete (needs >=5 items and  anchors).")
        handoff_actions.append("Repair  delivery board entries to include  anchors.")

    if " Advanced GitHub Actions Reference" in integration_expansion_workflow_text:
        wins.append(" workflow reference remains available for weekly KPI baseline review.")
    else:
        misses.append(" workflow reference is missing for weekly review context.")
        handoff_actions.append(
            "Restore integration_expansion workflow reference before publishing  outcomes."
        )

    if not failed and not critical_failures:
        wins.append(
            " weekly review closeout lane is fully complete and ready for  integration expansion #2."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "weekly-review-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "integration_expansion_summary": str(integration_expansion_summary.relative_to(root))
            if integration_expansion_summary.exists()
            else str(integration_expansion_summary),
            "integration_expansion_delivery_board": str(
                integration_expansion_board.relative_to(root)
            )
            if integration_expansion_board.exists()
            else str(integration_expansion_board),
            "integration_expansion_workflow": _INTEGRATION_EXPANSION_WORKFLOW_PATH,
        },
        "checks": checks,
        "rollup": {
            "integration_expansion_activation_score": integration_expansion_score,
            "integration_expansion_checks": integration_expansion_check_count,
            "integration_expansion_delivery_board_items": board_count,
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
        "Weekly Review Closeout summary",
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
        target / "weekly-review-closeout-2-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "weekly-review-closeout-2-summary.md", _render_text(payload) + "\n")
    _write(
        target / "weekly-review-closeout-2-weekly-brief.md",
        "#  weekly brief\n",
    )
    _write(
        target / "weekly-review-closeout-2-kpi-dashboard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(
        target / "weekly-review-closeout-2-governance-decision-register.md",
        "#  governance decision register\n",
    )
    _write(
        target / "weekly-review-closeout-2-risk-ledger.csv",
        "risk_id,severity,owner,mitigation,status\n",
    )
    _write(target / "weekly-review-closeout-2-execution-log.md", "#  execution log\n")
    _write(
        target / "weekly-review-closeout-2-delivery-board.md",
        "\n".join(["#  delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "weekly-review-closeout-2-validation-commands.md",
        "#  validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "weekly-review-closeout-2-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_weekly_review_closeout_summary_impl(root: Path) -> dict[str, Any]:
    "Compatibility alias for legacy -based builder name."
    return build_weekly_review_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=" weekly review closeout checks")
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

    payload = build_weekly_review_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/weekly-review-closeout-2-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
