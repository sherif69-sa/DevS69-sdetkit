from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-phase2-hardening-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY57_SUMMARY_PATH = (
    "docs/artifacts/kpi-deep-audit-closeout-pack/kpi-deep-audit-closeout-summary.json"
)
_DAY57_BOARD_PATH = "docs/artifacts/kpi-deep-audit-closeout-pack/kpi-deep-audit-delivery-board.md"
_SECTION_HEADER = '#  — Phase-2 hardening closeout lane'
_REQUIRED_SECTIONS = [
    '## Why  matters',
    '## Required inputs ()',
    '##  command lane',
    "## Phase-2 hardening contract",
    "## Phase-2 hardening quality checklist",
    '##  delivery board',
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit phase2-hardening-closeout --format json --strict",
    "python -m sdetkit phase2-hardening-closeout --emit-pack-dir docs/artifacts/phase2-hardening-closeout-pack --format json --strict",
    "python -m sdetkit phase2-hardening-closeout --execute --evidence-dir docs/artifacts/phase2-hardening-closeout-pack/evidence --format json --strict",
    "python scripts/check_phase2_hardening_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit phase2-hardening-closeout --format json --strict",
    "python -m sdetkit phase2-hardening-closeout --emit-pack-dir docs/artifacts/phase2-hardening-closeout-pack --format json --strict",
    "python scripts/check_phase2_hardening_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    'Single owner + backup reviewer are assigned for  Phase-2 hardening execution and signal triage.',
    'The  lane references  KPI deep-audit outcomes and unresolved risks.',
    'Every  section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.',
    ' closeout records hardening outcomes and  pre-plan priorities.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes friction-map digest, page hardening actions, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI",
    "- [ ] Artifact pack includes hardening brief, risk ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  Phase-2 hardening brief committed',
    '- [ ]  hardening plan reviewed with owner + backup',
    '- [ ]  risk ledger exported',
    '- [ ]  KPI scorecard snapshot exported',
    '- [ ]  pre-plan priorities drafted from  learnings',
]

_DEFAULT_PAGE_TEMPLATE = '#  — Phase-2 hardening closeout lane\n\n closes with a major Phase-2 hardening upgrade that turns  KPI deep-audit outcomes into deterministic execution hardening governance.\n\n## Why  matters\n\n- Converts  KPI deep-audit evidence into repeatable hardening execution loops.\n- Protects quality with ownership, command proof, and KPI rollback guardrails.\n- Produces a deterministic handoff from  closeout into  pre-plan execution planning.\n\n## Required inputs ()\n\n- `docs/artifacts/kpi-deep-audit-closeout-pack/kpi-deep-audit-closeout-summary.json`\n- `docs/artifacts/kpi-deep-audit-closeout-pack/kpi-deep-audit-delivery-board.md`\n\n##  command lane\n\n```bash\npython -m sdetkit phase2-hardening-closeout --format json --strict\npython -m sdetkit phase2-hardening-closeout --emit-pack-dir docs/artifacts/phase2-hardening-closeout-pack --format json --strict\npython -m sdetkit phase2-hardening-closeout --execute --evidence-dir docs/artifacts/phase2-hardening-closeout-pack/evidence --format json --strict\npython scripts/check_phase2_hardening_closeout_contract.py\n```\n\n## Phase-2 hardening contract\n\n- Single owner + backup reviewer are assigned for  Phase-2 hardening execution and signal triage.\n- The  lane references  KPI deep-audit outcomes and unresolved risks.\n- Every  section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n-  closeout records hardening outcomes and  pre-plan priorities.\n\n## Phase-2 hardening quality checklist\n\n- [ ] Includes friction-map digest, page hardening actions, and rollback strategy\n- [ ] Every section has owner, review window, KPI threshold, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI\n- [ ] Artifact pack includes hardening brief, risk ledger, KPI scorecard, and execution log\n\n##  delivery board\n\n- [ ]  Phase-2 hardening brief committed\n- [ ]  hardening plan reviewed with owner + backup\n- [ ]  risk ledger exported\n- [ ]  KPI scorecard snapshot exported\n- [ ]  pre-plan priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 35 points.\n- Phase-2 hardening contract lock + delivery board readiness: 15 points.\n'


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


def _load_kpi_deep_audit(path: Path) -> tuple[int, bool, int]:
    payload_obj = _load_json(path)
    if not isinstance(payload_obj, dict):
        return 0, False, 0
    summary_obj = payload_obj.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    checks_obj = payload_obj.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    return (
        int(summary.get("activation_score", 0)),
        coerce_bool(summary.get("strict_pass", False), default=False),
        len(checks),
    )


def _load_board(path: Path) -> tuple[int, bool]:
    text = _read(path)
    lines = [line.strip() for line in text.splitlines()]
    items = [line for line in lines if line.startswith("- [")]
    has_kpi_deep_audit = any('' in line for line in lines)
    return len(items), has_kpi_deep_audit


def build_phase2_hardening_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    top10_text = _read(root / _TOP10_PATH)
    page_text = _read(root / _PAGE_PATH)
    kpi_deep_audit_summary = root / _DAY57_SUMMARY_PATH
    kpi_deep_audit_board = root / _DAY57_BOARD_PATH

    kpi_deep_audit_score, kpi_deep_audit_strict, kpi_deep_audit_check_count = _load_kpi_deep_audit(
        kpi_deep_audit_summary
    )
    board_count, board_has_kpi_deep_audit = _load_board(kpi_deep_audit_board)

    missing_sections = [s for s in _REQUIRED_SECTIONS if s not in page_text]
    missing_commands = [c for c in _REQUIRED_COMMANDS if c not in page_text]
    missing_contract_lines = [line for line in _REQUIRED_CONTRACT_LINES if line not in page_text]
    missing_quality_lines = [line for line in _REQUIRED_QUALITY_LINES if line not in page_text]
    missing_board_items = [line for line in _REQUIRED_DELIVERY_BOARD_LINES if line not in page_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_integration_link",
            "weight": 8,
            "passed": _PAGE_PATH in readme_text,
            "evidence": _PAGE_PATH,
        },
        {
            "check_id": "readme_command_lane",
            "weight": 4,
            "passed": "phase2-hardening-closeout" in readme_text,
            "evidence": "README phase2-hardening-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-58-big-upgrade-report.md" in docs_index_text
                and "integrations-phase2-hardening-closeout.md" in docs_index_text
            ),
            "evidence": "impact-58-big-upgrade-report.md + integrations-phase2-hardening-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ('' in top10_text and '' in top10_text),
            "evidence": ' +  strategy chain',
        },
        {
            "check_id": "kpi_deep_audit_summary_present",
            "weight": 10,
            "passed": kpi_deep_audit_summary.exists(),
            "evidence": str(kpi_deep_audit_summary),
        },
        {
            "check_id": "kpi_deep_audit_delivery_board_present",
            "weight": 8,
            "passed": kpi_deep_audit_board.exists(),
            "evidence": str(kpi_deep_audit_board),
        },
        {
            "check_id": "kpi_deep_audit_quality_floor",
            "weight": 15,
            "passed": kpi_deep_audit_strict and kpi_deep_audit_score >= 95,
            "evidence": {
                "kpi_deep_audit_score": kpi_deep_audit_score,
                "strict_pass": kpi_deep_audit_strict,
                "kpi_deep_audit_checks": kpi_deep_audit_check_count,
            },
        },
        {
            "check_id": "kpi_deep_audit_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_kpi_deep_audit,
            "evidence": {
                "board_items": board_count,
                "contains_kpi_deep_audit": board_has_kpi_deep_audit,
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
    if not kpi_deep_audit_summary.exists() or not kpi_deep_audit_board.exists():
        critical_failures.append("kpi_deep_audit_handoff_inputs")
    if not kpi_deep_audit_strict:
        critical_failures.append("kpi_deep_audit_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if kpi_deep_audit_strict:
        wins.append(
            f"57 continuity is strict-pass with activation score={kpi_deep_audit_score}."
        )
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  KPI deep-audit closeout command and restore strict baseline before  lock.'
        )

    if board_count >= 5 and board_has_kpi_deep_audit:
        wins.append(
            f"57 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and  anchors).'
        )
        handoff_actions.append('Repair  delivery board entries to include  anchors.')

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Phase-2 hardening contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Phase-2 hardening contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            'Complete all  contract lines, quality checklist entries, and delivery board tasks in docs.'
        )

    if not failed and not critical_failures:
        wins.append(
            ' Phase-2 hardening closeout lane is fully complete and ready for  pre-plan lane.'
        )

    score = int(round(sum(c["weight"] for c in checks if bool(c["passed"]))))
    return {
        "name": "phase2-hardening-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "kpi_deep_audit_summary": str(kpi_deep_audit_summary.relative_to(root))
            if kpi_deep_audit_summary.exists()
            else str(kpi_deep_audit_summary),
            "kpi_deep_audit_delivery_board": str(kpi_deep_audit_board.relative_to(root))
            if kpi_deep_audit_board.exists()
            else str(kpi_deep_audit_board),
        },
        "checks": checks,
        "rollup": {
            "kpi_deep_audit_activation_score": kpi_deep_audit_score,
            "kpi_deep_audit_checks": kpi_deep_audit_check_count,
            "kpi_deep_audit_delivery_board_items": board_count,
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
        'Phase 2 Hardening Closeout summary (legacy: )',
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
        target / "phase2-hardening-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "phase2-hardening-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "phase2-hardening-brief.md", '#  Phase-2 hardening brief\n')
    _write(target / "phase2-hardening-risk-ledger.csv", "risk,owner,mitigation,status\n")
    _write(target / "phase2-hardening-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "phase2-hardening-execution-log.md", '#  execution log\n')
    _write(
        target / "phase2-hardening-delivery-board.md",
        "\n".join(['#  delivery board', *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "phase2-hardening-validation-commands.md",
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
        out_dir / "phase2-hardening-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_phase2_hardening_closeout_summary_impl(root: Path) -> dict[str, Any]:
    'Compatibility alias for legacy -based builder name.'
    return build_phase2_hardening_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 2 Hardening Closeout checks")
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

    payload = build_phase2_hardening_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/phase2-hardening-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
