from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-kpi-deep-audit-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY56_SUMMARY_PATH = (
    "docs/artifacts/stabilization-closeout-pack/stabilization-closeout-summary.json"
)
_DAY56_BOARD_PATH = "docs/artifacts/stabilization-closeout-pack/stabilization-delivery-board.md"
_unused_SECTION_HEADER = '#  — KPI deep audit closeout lane'
_REQUIRED_SECTIONS = [
    '## Why  matters',
    '## Required inputs ()',
    '##  command lane',
    "## KPI deep audit contract",
    "## KPI deep audit quality checklist",
    '##  delivery board',
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit kpi-deep-audit-closeout --format json --strict",
    "python -m sdetkit kpi-deep-audit-closeout --emit-pack-dir docs/artifacts/kpi-deep-audit-closeout-pack --format json --strict",
    "python -m sdetkit kpi-deep-audit-closeout --execute --evidence-dir docs/artifacts/kpi-deep-audit-closeout-pack/evidence --format json --strict",
    "python scripts/check_kpi_deep_audit_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit kpi-deep-audit-closeout --format json --strict",
    "python -m sdetkit kpi-deep-audit-closeout --emit-pack-dir docs/artifacts/kpi-deep-audit-closeout-pack --format json --strict",
    "python scripts/check_kpi_deep_audit_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    'Single owner + backup reviewer are assigned for  KPI deep-audit execution and signal triage.',
    'The  lane references  stabilization outcomes and unresolved risks.',
    'Every  section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.',
    ' closeout records deep-audit outcomes and  execution priorities.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes KPI trendline digest, anomaly triage, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI",
    "- [ ] Artifact pack includes audit brief, risk ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  KPI deep audit brief committed',
    '- [ ]  deep-audit plan reviewed with owner + backup',
    '- [ ]  risk ledger exported',
    '- [ ]  KPI scorecard snapshot exported',
    '- [ ]  execution priorities drafted from  learnings',
]

_DEFAULT_PAGE_TEMPLATE = '#  — KPI deep audit closeout lane\n\n closes with a major KPI deep-audit upgrade that turns  stabilization outcomes into deterministic trendline governance.\n\n## Why  matters\n\n- Converts  stabilization evidence into repeatable KPI anomaly triage loops.\n- Protects quality with ownership, command proof, and KPI rollback guardrails.\n- Produces a deterministic handoff from  closeout into  execution planning.\n\n## Required inputs ()\n\n- `docs/artifacts/stabilization-closeout-pack/stabilization-closeout-summary.json`\n- `docs/artifacts/stabilization-closeout-pack/stabilization-delivery-board.md`\n\n##  command lane\n\n```bash\npython -m sdetkit kpi-deep-audit-closeout --format json --strict\npython -m sdetkit kpi-deep-audit-closeout --emit-pack-dir docs/artifacts/kpi-deep-audit-closeout-pack --format json --strict\npython -m sdetkit kpi-deep-audit-closeout --execute --evidence-dir docs/artifacts/kpi-deep-audit-closeout-pack/evidence --format json --strict\npython scripts/check_kpi_deep_audit_closeout_contract.py\n```\n\n## KPI deep audit contract\n\n- Single owner + backup reviewer are assigned for  KPI deep-audit execution and signal triage.\n- The  lane references  stabilization outcomes and unresolved risks.\n- Every  section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n-  closeout records deep-audit outcomes and  execution priorities.\n\n## KPI deep audit quality checklist\n\n- [ ] Includes KPI trendline digest, anomaly triage, and rollback strategy\n- [ ] Every section has owner, review window, KPI threshold, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI\n- [ ] Artifact pack includes audit brief, risk ledger, KPI scorecard, and execution log\n\n##  delivery board\n\n- [ ]  KPI deep audit brief committed\n- [ ]  deep-audit plan reviewed with owner + backup\n- [ ]  risk ledger exported\n- [ ]  KPI scorecard snapshot exported\n- [ ]  execution priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 35 points.\n- KPI deep-audit contract lock + delivery board readiness: 15 points.\n'


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


def _load_cycle56(path: Path) -> tuple[int, bool, int]:
    payload_obj = _load_json(path)
    if not isinstance(payload_obj, dict):
        return 0, False, 0
    summary_obj = payload_obj.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    checks_obj = payload_obj.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    score = int(summary.get("activation_score", 0) or 0)
    strict = coerce_bool(summary.get("strict_pass", False), default=False)
    return score, strict, len(checks)


def _load_board(path: Path) -> tuple[int, bool]:
    if not path.exists():
        return 0, False
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    items = [line for line in lines if line.startswith("- [")]
    has_cycle56 = any('' in line for line in lines)
    return len(items), has_cycle56


def build_kpi_deep_audit_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_path = root / _PAGE_PATH
    page_text = _read(page_path)
    top10_text = _read(root / _TOP10_PATH)
    summary = root / _DAY56_SUMMARY_PATH
    board = root / _DAY56_BOARD_PATH

    score, strict, check_count = _load_cycle56(summary)
    board_count, board_has_cycle56 = _load_board(board)

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
            "check_id": "readme_integration_link",
            "weight": 8,
            "passed": _PAGE_PATH in readme_text,
            "evidence": _PAGE_PATH,
        },
        {
            "check_id": "readme_command_lane",
            "weight": 4,
            "passed": "kpi-deep-audit-closeout" in readme_text,
            "evidence": "README kpi-deep-audit-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-57-big-upgrade-report.md" in docs_index_text
                and "integrations-kpi-deep-audit-closeout.md" in docs_index_text
            ),
            "evidence": "impact-57-big-upgrade-report.md + integrations-kpi-deep-audit-closeout.md",
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
            "weight": 10,
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
            "passed": board_count >= 5 and board_has_cycle56,
            "evidence": {"board_items": board_count, "contains": board_has_cycle56},
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
    if not summary.exists() or not board.exists():
        critical_failures.append("handoff_inputs")
    if not strict:
        critical_failures.append("strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if strict:
        wins.append(f"56 continuity is strict-pass with activation score={score}.")
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  stabilization closeout command and restore strict baseline before  lock.'
        )

    if board_count >= 5 and board_has_cycle56:
        wins.append(
            f"56 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and  anchors).'
        )
        handoff_actions.append('Repair  delivery board entries to include  anchors.')

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("KPI deep-audit contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "KPI deep-audit contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            'Complete all  contract lines, quality checklist entries, and delivery board tasks in docs.'
        )

    if not failed and not critical_failures:
        wins.append(
            ' KPI deep-audit closeout lane is fully complete and ready for  execution lane.'
        )

    score = int(round(sum(c["weight"] for c in checks if bool(c["passed"]))))
    return {
        "name": "kpi-deep-audit-closeout",
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
        'KPI Deep Audit Closeout summary (legacy: )',
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
    _write(target / "kpi-deep-audit-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "kpi-deep-audit-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "kpi-deep-audit-brief.md", '#  KPI deep-audit brief\n')
    _write(target / "kpi-deep-audit-risk-ledger.csv", "risk,owner,mitigation,status\n")
    _write(target / "kpi-deep-audit-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "kpi-deep-audit-execution-log.md", '#  execution log\n')
    _write(
        target / "kpi-deep-audit-delivery-board.md",
        "\n".join(['#  delivery board', *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "kpi-deep-audit-validation-commands.md",
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
        out_dir / "kpi-deep-audit-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_kpi_deep_audit_closeout_summary_impl(root: Path) -> dict[str, Any]:
    'Compatibility alias for legacy -based builder name.'
    return build_kpi_deep_audit_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KPI Deep Audit Closeout checks")
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

    payload = build_kpi_deep_audit_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/kpi-deep-audit-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
