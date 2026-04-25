from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-trust-assets-refresh-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY74_SUMMARY_PATH = (
    "docs/artifacts/distribution-scaling-closeout-pack/distribution-scaling-closeout-summary.json"
)
_DAY74_BOARD_PATH = (
    "docs/artifacts/distribution-scaling-closeout-pack/distribution-scaling-delivery-board.md"
)
_TRUST_PLAN_PATH = "docs/roadmap/plans/trust-assets-refresh-plan.json"
_BOARD_REQUIRED_ANCHOR = "distribution scaling plan committed"
_SECTION_HEADER = "# Lane — Trust assets refresh closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Lane matters",
    "## Required inputs (Lane)",
    "## Command lane",
    "## Trust assets refresh contract",
    "## Trust refresh quality checklist",
    "## Lane delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit trust-assets-refresh-closeout --format json --strict",
    "python -m sdetkit trust-assets-refresh-closeout --emit-pack-dir docs/artifacts/trust-assets-refresh-closeout-pack --format json --strict",
    "python scripts/check_trust_assets_refresh_closeout_contract.py --skip-evidence",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit trust-assets-refresh-closeout --format json --strict",
    "python -m sdetkit trust-assets-refresh-closeout --emit-pack-dir docs/artifacts/trust-assets-refresh-closeout-pack --format json --strict",
    "python scripts/check_trust_assets_refresh_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Lane trust assets refresh execution and signoff.",
    "This lane references Lane outcomes, controls, and KPI continuity signals.",
    "Every Lane section includes trust-surface CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Lane closeout records trust outcomes, confidence notes, and Lane contributor-recognition priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes trust-surface baseline, proof-link cadence, and stakeholder assumptions",
    "- [ ] Every trust lane row has owner, refresh window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures trust score delta, governance proof coverage delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, trust refresh plan, controls log, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Lane integration brief committed",
    "- [ ] Lane trust assets refresh plan committed",
    "- [ ] Lane trust controls and assumptions log exported",
    "- [ ] Lane trust KPI scorecard snapshot exported",
    "- [ ] Lane contributor-recognition priorities drafted from Lane learnings",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"trust_surfaces"',
    '"baseline"',
    '"target"',
    '"confidence"',
    '"owner"',
]

_DEFAULT_PAGE_TEMPLATE = "# Lane — Trust assets refresh closeout lane\n\nLane closes with a major upgrade that turns Lane distribution outcomes into a governance-grade trust refresh execution pack.\n\n## Why Lane matters\n\n- Converts Lane scaling proof into trust-surface upgrades across security, governance, and reliability docs.\n- Protects trust quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.\n- Creates a deterministic handoff from Lane trust refresh execution into Lane contributor recognition.\n\n## Required inputs (Lane)\n\n- `docs/artifacts/distribution-scaling-closeout-pack/distribution-scaling-closeout-summary.json`\n- `docs/artifacts/distribution-scaling-closeout-pack/distribution-scaling-delivery-board.md`\n- `docs/roadmap/plans/trust-assets-refresh-plan.json`\n\n## Command lane\n\n```bash\npython -m sdetkit trust-assets-refresh-closeout --format json --strict\npython -m sdetkit trust-assets-refresh-closeout --emit-pack-dir docs/artifacts/trust-assets-refresh-closeout-pack --format json --strict\npython scripts/check_trust_assets_refresh_closeout_contract.py --skip-evidence\n```\n\n## Trust assets refresh contract\n\n- Single owner + backup reviewer are assigned for Lane trust assets refresh execution and signoff.\n- This lane references Lane outcomes, controls, and KPI continuity signals.\n- Every Lane section includes trust-surface CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n- Lane closeout records trust outcomes, confidence notes, and Lane contributor-recognition priorities.\n\n## Trust refresh quality checklist\n\n- [ ] Includes trust-surface baseline, proof-link cadence, and stakeholder assumptions\n- [ ] Every trust lane row has owner, refresh window, KPI threshold, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures trust score delta, governance proof coverage delta, confidence, and rollback owner\n- [ ] Artifact pack includes integration brief, trust refresh plan, controls log, KPI scorecard, and execution log\n\n## Lane delivery board\n\n- [ ] Lane integration brief committed\n- [ ] Lane trust assets refresh plan committed\n- [ ] Lane trust controls and assumptions log exported\n- [ ] Lane trust KPI scorecard snapshot exported\n- [ ] Lane contributor-recognition priorities drafted from Lane learnings\n\n## Scoring model\n\nLane weighted score (0-100):\n\n- Contract + command lane integrity (35)\n- Lane continuity baseline quality (35)\n- Trust evidence data + delivery board completeness (30)\n\nStrict pass requires score >= 95 and zero critical failures.\n"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_distribution_scaling(summary_path: Path) -> tuple[int, bool, int]:
    if not summary_path.exists():
        return 0, False, 0
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    checks = data.get("checks", [])
    return (
        int(summary.get("activation_score", 0)),
        coerce_bool(summary.get("strict_pass", False), default=False),
        len(checks),
    )


def _count_board_items(board_path: Path, anchor: str) -> tuple[int, bool]:
    if not board_path.exists():
        return 0, False
    text = board_path.read_text(encoding="utf-8")
    items = [line for line in text.splitlines() if line.strip().startswith("- [")]
    return len(items), (anchor in text)


def build_trust_assets_refresh_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    trust_plan_text = _read(root / _TRUST_PLAN_PATH)

    distribution_scaling_summary = root / _DAY74_SUMMARY_PATH
    distribution_scaling_board = root / _DAY74_BOARD_PATH
    distribution_scaling_score, distribution_scaling_strict, distribution_scaling_check_count = (
        _load_distribution_scaling(distribution_scaling_summary)
    )
    board_count, board_has_distribution_scaling = _count_board_items(
        distribution_scaling_board, _BOARD_REQUIRED_ANCHOR
    )

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_plan_keys = [x for x in _REQUIRED_DATA_KEYS if x not in trust_plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_command_lane",
            "weight": 7,
            "passed": (
                "trust-assets-refresh-closeout" in readme_text
                or "trust-assets-refresh-closeout" in readme_text
            ),
            "evidence": "README trust-assets-refresh-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-75-big-upgrade-report.md" in docs_index_text
                and "integrations-trust-assets-refresh-closeout.md" in docs_index_text
            ),
            "evidence": "impact-75-big-upgrade-report.md + integrations-trust-assets-refresh-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": (
                "Trust assets refresh" in top10_text
                and "Contributor recognition board" in top10_text
            ),
            "evidence": "Trust assets refresh + Contributor recognition board strategy chain",
        },
        {
            "check_id": "distribution_scaling_summary_present",
            "weight": 10,
            "passed": distribution_scaling_summary.exists(),
            "evidence": str(distribution_scaling_summary),
        },
        {
            "check_id": "distribution_scaling_delivery_board_present",
            "weight": 7,
            "passed": distribution_scaling_board.exists(),
            "evidence": str(distribution_scaling_board),
        },
        {
            "check_id": "distribution_scaling_quality_floor",
            "weight": 13,
            "passed": distribution_scaling_strict and distribution_scaling_score >= 95,
            "evidence": {
                "distribution_scaling_score": distribution_scaling_score,
                "strict_pass": distribution_scaling_strict,
                "distribution_scaling_checks": distribution_scaling_check_count,
            },
        },
        {
            "check_id": "distribution_scaling_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_distribution_scaling,
            "evidence": {
                "board_items": board_count,
                "contains_distribution_scaling": board_has_distribution_scaling,
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
            "check_id": "trust_refresh_plan_data_present",
            "weight": 10,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _TRUST_PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not distribution_scaling_summary.exists() or not distribution_scaling_board.exists():
        critical_failures.append("distribution_scaling_handoff_inputs")
    if not distribution_scaling_strict:
        critical_failures.append("distribution_scaling_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if distribution_scaling_strict:
        wins.append(
            f"74 continuity is strict-pass with activation score={distribution_scaling_score}."
        )
    else:
        misses.append("74 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run 74 closeout command and restore strict baseline before lane 75 lock."
        )

    if board_count >= 5 and board_has_distribution_scaling:
        wins.append(f"74 delivery board integrity validated with {board_count} checklist items.")
    else:
        misses.append(
            "74 delivery board integrity is incomplete (needs >=5 items and anchor evidence)."
        )
        handoff_actions.append(
            "Repair 74 delivery board entries to include the distribution scaling anchor."
        )

    if not missing_plan_keys:
        wins.append("Lane trust assets refresh dataset is available for launch execution.")
    else:
        misses.append("Lane trust assets refresh dataset is missing required keys.")
        handoff_actions.append(
            "Update docs/roadmap/plans/trust-assets-refresh-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            "Lane trust assets refresh closeout lane is fully complete and ready for Lane contributor recognition."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "trust-assets-refresh-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "distribution_scaling_summary": str(distribution_scaling_summary.relative_to(root))
            if distribution_scaling_summary.exists()
            else str(distribution_scaling_summary),
            "distribution_scaling_delivery_board": str(distribution_scaling_board.relative_to(root))
            if distribution_scaling_board.exists()
            else str(distribution_scaling_board),
            "trust_refresh_plan": _TRUST_PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "distribution_scaling_activation_score": distribution_scaling_score,
            "distribution_scaling_checks": distribution_scaling_check_count,
            "distribution_scaling_delivery_board_items": board_count,
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
        "Trust Assets Refresh Closeout summary",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
    ]
    execution = payload.get("execution")
    if isinstance(execution, dict):
        lines.append(f"- Execute failed commands: {execution.get('failed_commands', [])}")
    return "\n".join(lines)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _emit_pack(root: Path, pack_dir: Path, payload: dict[str, Any]) -> None:
    target = pack_dir if pack_dir.is_absolute() else root / pack_dir
    _write(
        target / "trust-assets-refresh-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "trust-assets-refresh-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "trust-assets-refresh-integration-brief.md", "# Integration brief\n")
    _write(target / "trust-assets-refresh-plan.md", "# Trust assets refresh plan\n")
    _write(
        target / "trust-assets-refresh-trust-controls-log.json",
        json.dumps({"controls": []}, indent=2) + "\n",
    )
    _write(
        target / "trust-assets-refresh-trust-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(target / "trust-assets-refresh-execution-log.md", "# Execution log\n")
    _write(
        target / "trust-assets-refresh-delivery-board.md",
        "\n".join(["# Delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "trust-assets-refresh-validation-commands.md",
        "# Validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> dict[str, Any]:
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
        out_dir / "trust-assets-refresh-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )
    failed_commands = [idx for idx, event in enumerate(events, start=1) if event["returncode"] != 0]
    return {
        "total_commands": len(events),
        "failed_commands": failed_commands,
        "failed_count": len(failed_commands),
        "ok": not failed_commands,
    }


def build_trust_assets_refresh_closeout_summary_impl(root: Path) -> dict[str, Any]:
    "Compatibility alias for legacy lane-based builder name."
    return build_trust_assets_refresh_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trust Assets Refresh Closeout checks")
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

    payload = build_trust_assets_refresh_closeout_summary(root)

    execution_failed = False
    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/trust-assets-refresh-closeout-pack/evidence")
        )
        execution = _execute_commands(root, evidence_dir)
        payload["execution"] = execution
        execution_failed = not bool(execution.get("ok", False))

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    if execution_failed:
        return 1
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
