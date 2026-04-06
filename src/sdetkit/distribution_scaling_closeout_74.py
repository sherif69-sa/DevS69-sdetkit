from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-distribution-scaling-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY73_SUMMARY_PATH = (
    "docs/artifacts/case-study-launch-closeout-pack/case-study-launch-closeout-summary.json"
)
_DAY73_BOARD_PATH = (
    "docs/artifacts/case-study-launch-closeout-pack/case-study-launch-delivery-board.md"
)
_SCALING_PLAN_PATH = "docs/roadmap/plans/distribution-scaling-plan.json"
_SECTION_HEADER = '#  — Distribution scaling closeout lane'
_REQUIRED_SECTIONS = [
    '## Why  matters',
    '## Required inputs ()',
    '##  command lane',
    "## Distribution scaling contract",
    "## Distribution quality checklist",
    '##  delivery board',
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit distribution-scaling-closeout --format json --strict",
    "python -m sdetkit distribution-scaling-closeout --emit-pack-dir docs/artifacts/distribution-scaling-closeout-pack --format json --strict",
    "python -m sdetkit distribution-scaling-closeout --execute --evidence-dir docs/artifacts/distribution-scaling-closeout-pack/evidence --format json --strict",
    "python scripts/check_distribution_scaling_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit distribution-scaling-closeout --format json --strict",
    "python -m sdetkit distribution-scaling-closeout --emit-pack-dir docs/artifacts/distribution-scaling-closeout-pack --format json --strict",
    "python scripts/check_distribution_scaling_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    'Single owner + backup reviewer are assigned for  distribution scaling execution and signoff.',
    'The  lane references  publication outcomes, controls, and KPI continuity signals.',
    'Every  section includes channel CTA, runnable command CTA, KPI threshold, and rollback guardrail.',
    ' closeout records distribution outcomes, confidence notes, and  trust refresh priorities.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes channel mix baseline, treatment cadence, and audience-segment assumptions",
    "- [ ] Every channel plan row has owner, launch window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures CTR delta, qualified lead delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, scaling plan, controls log, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  integration brief committed',
    '- [ ]  distribution scaling plan committed',
    '- [ ]  channel controls and assumptions log exported',
    '- [ ]  KPI scorecard snapshot exported',
    '- [ ]  trust refresh priorities drafted from  learnings',
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"channels"',
    '"baseline"',
    '"target"',
    '"confidence"',
    '"owner"',
]

_DEFAULT_PAGE_TEMPLATE = '#  — Distribution scaling closeout lane\n\n closes with a major upgrade that turns  published case-study outcomes into a scalable distribution execution pack with governance safeguards.\n\n## Why  matters\n\n- Converts  publication proof into repeatable multi-channel distribution operations.\n- Protects scaling quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.\n- Creates a deterministic handoff from  distribution scaling execution into  trust-asset refresh.\n\n## Required inputs ()\n\n- `docs/artifacts/case-study-launch-closeout-pack/case-study-launch-closeout-summary.json`\n- `docs/artifacts/case-study-launch-closeout-pack/case-study-launch-delivery-board.md`\n- `docs/roadmap/plans/distribution-scaling-plan.json`\n\n##  command lane\n\n```bash\npython -m sdetkit distribution-scaling-closeout --format json --strict\npython -m sdetkit distribution-scaling-closeout --emit-pack-dir docs/artifacts/distribution-scaling-closeout-pack --format json --strict\npython -m sdetkit distribution-scaling-closeout --execute --evidence-dir docs/artifacts/distribution-scaling-closeout-pack/evidence --format json --strict\npython scripts/check_distribution_scaling_closeout_contract.py\n```\n\n## Distribution scaling contract\n\n- Single owner + backup reviewer are assigned for  distribution scaling execution and signoff.\n- The  lane references  publication outcomes, controls, and KPI continuity signals.\n- Every  section includes channel CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n-  closeout records distribution outcomes, confidence notes, and  trust refresh priorities.\n\n## Distribution quality checklist\n\n- [ ] Includes channel mix baseline, treatment cadence, and audience-segment assumptions\n- [ ] Every channel plan row has owner, launch window, KPI threshold, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures CTR delta, qualified lead delta, confidence, and rollback owner\n- [ ] Artifact pack includes integration brief, scaling plan, controls log, KPI scorecard, and execution log\n\n##  delivery board\n\n- [ ]  integration brief committed\n- [ ]  distribution scaling plan committed\n- [ ]  channel controls and assumptions log exported\n- [ ]  KPI scorecard snapshot exported\n- [ ]  trust refresh priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Contract + command lane integrity (35)\n-  continuity baseline quality (35)\n- Distribution evidence data + delivery board completeness (30)\n\nStrict pass requires score >= 95 and zero critical failures.\n'


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_prior_closeout(summary_path: Path) -> tuple[int, bool, int]:
    if not summary_path.exists():
        return 0, False, 0
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return 0, False, 0
    summary = payload.get("summary", {})
    checks = payload.get("checks", [])
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


def build_distribution_scaling_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    scaling_plan_text = _read(root / _SCALING_PLAN_PATH)

    prior_closeout_summary = root / _DAY73_SUMMARY_PATH
    prior_closeout_board = root / _DAY73_BOARD_PATH
    prior_closeout_score, prior_closeout_strict, prior_closeout_check_count = _load_prior_closeout(
        prior_closeout_summary
    )
    board_count, board_has_prior_closeout = _count_board_items(prior_closeout_board, '')

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_scaling_plan_keys = [x for x in _REQUIRED_DATA_KEYS if x not in scaling_plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_command_lane",
            "weight": 7,
            "passed": (
                "distribution-scaling-closeout" in readme_text
                or "distribution-scaling-closeout" in readme_text
            ),
            "evidence": "README distribution-scaling-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-74-big-upgrade-report.md" in docs_index_text
                and "integrations-distribution-scaling-closeout.md" in docs_index_text
            ),
            "evidence": "impact-74-big-upgrade-report.md + integrations-distribution-scaling-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ('' in top10_text and '' in top10_text),
            "evidence": ' +  strategy chain',
        },
        {
            "check_id": "prior_closeout_summary_present",
            "weight": 10,
            "passed": prior_closeout_summary.exists(),
            "evidence": str(prior_closeout_summary),
        },
        {
            "check_id": "prior_closeout_delivery_board_present",
            "weight": 7,
            "passed": prior_closeout_board.exists(),
            "evidence": str(prior_closeout_board),
        },
        {
            "check_id": "prior_closeout_quality_floor",
            "weight": 13,
            "passed": prior_closeout_strict and prior_closeout_score >= 95,
            "evidence": {
                "prior_closeout_score": prior_closeout_score,
                "strict_pass": prior_closeout_strict,
                "prior_closeout_checks": prior_closeout_check_count,
            },
        },
        {
            "check_id": "prior_closeout_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_prior_closeout,
            "evidence": {
                "board_items": board_count,
                "contains_prior_closeout": board_has_prior_closeout,
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
            "check_id": "distribution_plan_data_present",
            "weight": 10,
            "passed": not missing_scaling_plan_keys,
            "evidence": missing_scaling_plan_keys or _SCALING_PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not prior_closeout_summary.exists() or not prior_closeout_board.exists():
        critical_failures.append("prior_closeout_handoff_inputs")
    if not prior_closeout_strict:
        critical_failures.append("prior_closeout_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if prior_closeout_strict:
        wins.append(
            f"73 continuity is strict-pass with activation score={prior_closeout_score}."
        )
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  closeout command and restore strict baseline before  lock.'
        )

    if board_count >= 5 and board_has_prior_closeout:
        wins.append(
            f"73 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and  anchors).'
        )
        handoff_actions.append('Repair  delivery board entries to include  anchors.')

    if not missing_scaling_plan_keys:
        wins.append(' distribution scaling dataset is available for launch execution.')
    else:
        misses.append(' distribution scaling dataset is missing required keys.')
        handoff_actions.append(
            "Update docs/roadmap/plans/distribution-scaling-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            ' distribution scaling closeout lane is fully complete and ready for  trust refresh.'
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "distribution-scaling-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "prior_closeout_summary": str(prior_closeout_summary.relative_to(root))
            if prior_closeout_summary.exists()
            else str(prior_closeout_summary),
            "prior_closeout_delivery_board": str(prior_closeout_board.relative_to(root))
            if prior_closeout_board.exists()
            else str(prior_closeout_board),
            "distribution_scaling_plan": _SCALING_PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "prior_closeout_activation_score": prior_closeout_score,
            "prior_closeout_checks": prior_closeout_check_count,
            "prior_closeout_delivery_board_items": board_count,
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
        "Distribution Scaling Closeout summary",
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
        target / "distribution-scaling-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "distribution-scaling-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "distribution-scaling-integration-brief.md", '#  integration brief\n')
    _write(target / "distribution-scaling-plan.md", '#  distribution scaling plan\n')
    _write(
        target / "distribution-scaling-channel-controls-log.json",
        json.dumps({"controls": []}, indent=2) + "\n",
    )
    _write(
        target / "distribution-scaling-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(target / "distribution-scaling-execution-log.md", '#  execution log\n')
    _write(
        target / "distribution-scaling-delivery-board.md",
        "\n".join(['#  delivery board', *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "distribution-scaling-validation-commands.md",
        '#  validation commands\n\n```bash\n' + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "distribution-scaling-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_distribution_scaling_closeout_summary_impl(root: Path) -> dict[str, Any]:
    'Compatibility alias for legacy -based builder name.'
    return build_distribution_scaling_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Distribution Scaling Closeout checks")
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

    payload = build_distribution_scaling_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/distribution-scaling-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
