from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-community-program-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY61_SUMMARY_PATH = (
    "docs/artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-closeout-summary.json"
)
_DAY61_BOARD_PATH = "docs/artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-delivery-board.md"
_SECTION_HEADER = '#  — Community program setup closeout lane'
_REQUIRED_SECTIONS = [
    "## Why Community Program Closeout matters",
    '## Required inputs ()',
    "## Community Program Closeout command lane",
    "## Community program execution contract",
    "## Community program quality checklist",
    "## Community Program Closeout delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit community-program-closeout --format json --strict",
    "python -m sdetkit community-program-closeout --emit-pack-dir docs/artifacts/community-program-closeout-pack --format json --strict",
    "python -m sdetkit community-program-closeout --execute --evidence-dir docs/artifacts/community-program-closeout-pack/evidence --format json --strict",
    "python scripts/check_community_program_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit community-program-closeout --format json --strict",
    "python -m sdetkit community-program-closeout --emit-pack-dir docs/artifacts/community-program-closeout-pack --format json --strict",
    "python scripts/check_community_program_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    'Single owner + backup reviewer are assigned for  community office-hours execution and moderation safety.',
    'The  lane references  Phase-3 kickoff outcomes, trust guardrails, and KPI continuity evidence.',
    'Every  section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.',
    ' closeout records office-hours cadence, participation rules, moderation SOPs, and  onboarding priorities.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes office-hours calendar, participation policy, escalation flow, and rollback trigger",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures attendance target, response SLA, trust incidents, confidence, and recovery owner",
    "- [ ] Artifact pack includes launch brief, participation policy, moderation runbook, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  community launch brief committed',
    '- [ ]  office-hours cadence published',
    '- [ ]  participation policy + moderation SOP exported',
    '- [ ]  KPI scorecard snapshot exported',
    '- [ ]  onboarding priorities drafted from  learnings',
]

_DEFAULT_PAGE_TEMPLATE = '#  — Community program setup closeout lane\n\n ships a major community-program upgrade that converts  kickoff evidence into a deterministic community operations lane.\n\n## Why Community Program Closeout matters\n\n- Converts  trust baseline into repeatable office-hours and participation loops.\n- Protects community trust outcomes with ownership, command proof, and moderation rollback guardrails.\n- Produces a deterministic handoff from  community setup into  contributor onboarding activation.\n\n## Required inputs ()\n\n- `docs/artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-closeout-summary.json`\n- `docs/artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-delivery-board.md`\n\n## Community Program Closeout command lane\n\n```bash\npython -m sdetkit community-program-closeout --format json --strict\npython -m sdetkit community-program-closeout --emit-pack-dir docs/artifacts/community-program-closeout-pack --format json --strict\npython -m sdetkit community-program-closeout --execute --evidence-dir docs/artifacts/community-program-closeout-pack/evidence --format json --strict\npython scripts/check_community_program_closeout_contract.py\n```\n\n## Community program execution contract\n\n- Single owner + backup reviewer are assigned for  community office-hours execution and moderation safety.\n- The  lane references  Phase-3 kickoff outcomes, trust guardrails, and KPI continuity evidence.\n- Every  section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n-  closeout records office-hours cadence, participation rules, moderation SOPs, and  onboarding priorities.\n\n## Community program quality checklist\n\n- [ ] Includes office-hours calendar, participation policy, escalation flow, and rollback trigger\n- [ ] Every section has owner, review window, KPI threshold, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures attendance target, response SLA, trust incidents, confidence, and recovery owner\n- [ ] Artifact pack includes launch brief, participation policy, moderation runbook, and execution log\n\n## Community Program Closeout delivery board\n\n- [ ]  community launch brief committed\n- [ ]  office-hours cadence published\n- [ ]  participation policy + moderation SOP exported\n- [ ]  KPI scorecard snapshot exported\n- [ ]  onboarding priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 35 points.\n- Community program contract lock + delivery board readiness: 15 points.\n'


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


def _load_cycle61(path: Path) -> tuple[int, bool, int]:
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


def build_community_program_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)

    summary = root / _DAY61_SUMMARY_PATH
    board = root / _DAY61_BOARD_PATH
    score, strict, check_count = _load_cycle61(summary)
    board_count, board_has_cycle61 = _count_board_items(board, '')

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_command_lane",
            "weight": 7,
            "passed": ("community-program-closeout" in readme_text),
            "evidence": "README community-program-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-62-big-upgrade-report.md" in docs_index_text
                and "integrations-community-program-closeout.md" in docs_index_text
            ),
            "evidence": "impact-62-big-upgrade-report.md + integrations-community-program-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ('' in top10_text and '' in top10_text),
            "evidence": ' +  strategy chain',
        },
        {
            "check_id": "summary_present",
            "weight": 10,
            "passed": summary.exists(),
            "evidence": str(summary),
        },
        {
            "check_id": "delivery_board_present",
            "weight": 8,
            "passed": board.exists(),
            "evidence": str(board),
        },
        {
            "check_id": "quality_floor",
            "weight": 15,
            "passed": strict and score >= 95,
            "evidence": {
                "score": score,
                "strict_pass": strict,
                "checks": check_count,
            },
        },
        {
            "check_id": "board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_cycle61,
            "evidence": {"board_items": board_count, "contains": board_has_cycle61},
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
    if not summary.exists() or not board.exists():
        critical_failures.append("handoff_inputs")
    if not strict:
        critical_failures.append("strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if strict:
        wins.append(f"61 continuity is strict-pass with activation score={score}.")
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  Phase-3 kickoff closeout command and restore strict baseline before  lock.'
        )

    if board_count >= 5 and board_has_cycle61:
        wins.append(
            f"61 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and  anchors).'
        )
        handoff_actions.append('Repair  delivery board entries to include  anchors.')

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Community program contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Community program contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            'Complete all  contract lines, quality checklist entries, and delivery board tasks in docs.'
        )

    if not failed and not critical_failures:
        wins.append(
            ' community program closeout lane is fully complete and ready for  onboarding execution lane.'
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "community-program-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "summary": str(summary.relative_to(root))
            if summary.exists()
            else str(summary),
            "delivery_board": str(board.relative_to(root))
            if board.exists()
            else str(board),
        },
        "checks": checks,
        "rollup": {
            "activation_score": score,
            "checks": check_count,
            "delivery_board_items": board_count,
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
        "Community Program Closeout summary",
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
        target / "community-program-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "community-program-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "community-program-community-launch-brief.md", '#  community launch brief\n'
    )
    _write(
        target / "community-program-office-hours-cadence.md",
        '#  office-hours cadence\n\n- Weekly office hours\n',
    )
    _write(target / "community-program-participation-policy.md", '#  participation policy\n')
    _write(target / "community-program-moderation-runbook.md", '#  moderation runbook\n')
    _write(
        target / "community-program-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n"
    )
    _write(target / "community-program-execution-log.md", '#  execution log\n')
    _write(
        target / "community-program-delivery-board.md",
        "\n".join(['#  delivery board', *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "community-program-validation-commands.md",
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
        out_dir / "community-program-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_community_program_closeout_summary_impl(root: Path) -> dict[str, Any]:
    'Compatibility alias for legacy -based builder name.'
    return build_community_program_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=' community program closeout checks')
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

    payload = build_community_program_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/community-program-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
