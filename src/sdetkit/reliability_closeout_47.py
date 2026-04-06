from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-reliability-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY46_SUMMARY_PATH = "docs/artifacts/optimization-closeout-pack/optimization-closeout-summary.json"
_DAY46_SUMMARY_LEGACY_PATH = (
    "docs/artifacts/optimization-closeout-pack-46/optimization-closeout-summary-46.json"
)
_DAY46_BOARD_PATH = "docs/artifacts/optimization-closeout-pack/optimization-delivery-board.md"
_DAY46_BOARD_LEGACY_PATH = "docs/artifacts/optimization-closeout-pack-46/delivery-board-46.md"
_SECTION_HEADER = '#  — Reliability closeout lane'
_REQUIRED_SECTIONS = [
    '## Why  matters',
    '## Required inputs ()',
    '##  command lane',
    "## Reliability closeout contract",
    "## Reliability quality checklist",
    '##  delivery board',
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit reliability-closeout --format json --strict",
    "python -m sdetkit reliability-closeout --emit-pack-dir docs/artifacts/reliability-closeout-pack-47 --format json --strict",
    "python -m sdetkit reliability-closeout --execute --evidence-dir docs/artifacts/reliability-closeout-pack-47/evidence --format json --strict",
    "python scripts/check_reliability_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit reliability-closeout --format json --strict",
    "python -m sdetkit reliability-closeout --emit-pack-dir docs/artifacts/reliability-closeout-pack-47 --format json --strict",
    "python scripts/check_reliability_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    'Single owner + backup reviewer are assigned for  reliability lane execution and KPI follow-up.',
    'The  reliability lane references  optimization winners and misses with deterministic reliability loops.',
    'Every  section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.',
    ' closeout records reliability learnings and  execution priorities.',
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes reliability summary, incident map, and rollback strategy",
    "- [ ] Every section has owner, publish window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes reliability plan, incident map, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    '- [ ]  reliability plan draft committed',
    '- [ ]  review notes captured with owner + backup',
    '- [ ]  incident map exported',
    '- [ ]  KPI scorecard snapshot exported',
    '- [ ]  execution priorities drafted from  learnings',
]

_DEFAULT_PAGE_TEMPLATE = '#  — Reliability closeout lane\n\n closes with a major reliability upgrade that converts  optimization evidence into deterministic hardening loops.\n\n## Why  matters\n\n- Converts  optimization proof into reliability-first operating motion.\n- Protects quality with owner accountability, command proof, and KPI guardrails.\n- Produces a deterministic handoff from reliability outcomes into  execution priorities.\n\n## Required inputs ()\n\n- `docs/artifacts/optimization-closeout-pack/optimization-closeout-summary.json`\n- `docs/artifacts/optimization-closeout-pack/optimization-delivery-board.md`\n\n##  command lane\n\n```bash\npython -m sdetkit reliability-closeout --format json --strict\npython -m sdetkit reliability-closeout --emit-pack-dir docs/artifacts/reliability-closeout-pack-47 --format json --strict\npython -m sdetkit reliability-closeout --execute --evidence-dir docs/artifacts/reliability-closeout-pack-47/evidence --format json --strict\npython scripts/check_reliability_closeout_contract.py\n```\n\n## Reliability closeout contract\n\n- Single owner + backup reviewer are assigned for  reliability lane execution and KPI follow-up.\n- The  reliability lane references  optimization winners and misses with deterministic reliability loops.\n- Every  section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.\n-  closeout records reliability learnings and  execution priorities.\n\n## Reliability quality checklist\n\n- [ ] Includes reliability summary, incident map, and rollback strategy\n- [ ] Every section has owner, publish window, KPI target, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI\n- [ ] Artifact pack includes reliability plan, incident map, KPI scorecard, and execution log\n\n##  delivery board\n\n- [ ]  reliability plan draft committed\n- [ ]  review notes captured with owner + backup\n- [ ]  incident map exported\n- [ ]  KPI scorecard snapshot exported\n- [ ]  execution priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Docs contract + command lane completeness: 30 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 35 points.\n- Reliability contract lock + delivery board readiness: 15 points.\n'


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


def _load_cycle46(path: Path) -> tuple[float, bool, int]:
    data = _load_json(path)
    if data is None:
        return 0.0, False, 0
    summary = data.get("summary")
    checks = data.get("checks")
    score = summary.get("activation_score") if isinstance(summary, dict) else None
    strict_pass = summary.get("strict_pass") if isinstance(summary, dict) else False
    count = len(checks) if isinstance(checks, list) else 0
    return float(score or 0.0), bool(strict_pass), count


def _board_stats(path: Path) -> tuple[int, bool, bool]:
    text = _read(path)
    items = [line for line in text.splitlines() if line.strip().startswith("- [")]
    return len(items), '' in text, '' in text


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def _resolve_existing_path(root: Path, primary: str, legacy: str) -> Path:
    primary_path = root / primary
    if primary_path.exists():
        return primary_path
    legacy_path = root / legacy
    if legacy_path.exists():
        return legacy_path
    return primary_path


def build_reliability_closeout_summary(root: Path) -> dict[str, Any]:
    readme_path = "README.md"
    docs_index_path = "docs/index.md"
    docs_page_path = _PAGE_PATH
    top10_path = _TOP10_PATH

    readme_text = _read(root / readme_path)
    docs_index_text = _read(root / docs_index_path)
    page_path = root / docs_page_path
    page_text = _read(page_path)
    top10_text = _read(root / top10_path)

    missing_sections = [s for s in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if s not in page_text]
    missing_commands = [c for c in _REQUIRED_COMMANDS if c not in page_text]
    missing_contract_lines = _contains_all_lines(
        page_text, [f"- {line}" for line in _REQUIRED_CONTRACT_LINES]
    )
    missing_quality_lines = _contains_all_lines(page_text, _REQUIRED_QUALITY_LINES)
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    summary_primary = root / _DAY46_SUMMARY_PATH
    board_primary = root / _DAY46_BOARD_PATH
    summary = _resolve_existing_path(root, _DAY46_SUMMARY_PATH, _DAY46_SUMMARY_LEGACY_PATH)
    board = _resolve_existing_path(root, _DAY46_BOARD_PATH, _DAY46_BOARD_LEGACY_PATH)
    score, strict, check_count = _load_cycle46(summary)
    board_count, board_has_cycle46, board_has_cycle47 = _board_stats(board)

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
            "passed": "docs/integrations-reliability-closeout.md" in readme_text,
            "evidence": "docs/integrations-reliability-closeout.md",
        },
        {
            "check_id": "readme_command_lane",
            "weight": 4,
            "passed": ("reliability-closeout" in readme_text)
            or ("cycle47-reliability-closeout" in readme_text),
            "evidence": "reliability-closeout (legacy: cycle47-reliability-closeout)",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-47-big-upgrade-report.md" in docs_index_text
                and "integrations-reliability-closeout.md" in docs_index_text
            ),
            "evidence": "impact-47-big-upgrade-report.md + integrations-reliability-closeout.md",
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
            "passed": board_count >= 5 and board_has_cycle46 and board_has_cycle47,
            "evidence": {
                "board_items": board_count,
                "contains": board_has_cycle46,
                "contains": board_has_cycle47,
            },
        },
        {
            "check_id": "reliability_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "reliability_quality_checklist_locked",
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
    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    critical_failures: list[str] = []
    if not summary.exists() or not board.exists():
        critical_failures.append("handoff_inputs")
    if not strict:
        critical_failures.append("strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if strict:
        wins.append(f"46 continuity is strict-pass with activation score={score}.")
    else:
        misses.append(' strict continuity signal is missing.')
        handoff_actions.append(
            'Re-run  optimization closeout command and restore strict pass baseline before  lock.'
        )

    if board_count >= 5 and board_has_cycle46 and board_has_cycle47:
        wins.append(
            f"46 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            ' delivery board integrity is incomplete (needs >=5 items and /47 anchors).'
        )
        handoff_actions.append(
            'Repair  delivery board entries to include  and  anchors.'
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Reliability execution contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Reliability contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            'Complete all  reliability contract lines, quality checklist entries, and delivery board tasks in docs.'
        )

    if not failed and not critical_failures:
        wins.append(
            ' reliability closeout lane is fully complete and ready for  execution lane.'
        )

    return {
        "name": "reliability-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "summary": str(summary.relative_to(root))
            if summary.exists()
            else str(summary),
            "summary_primary": str(summary_primary.relative_to(root)),
            "delivery_board": str(board.relative_to(root))
            if board.exists()
            else str(board),
            "delivery_board_primary": str(board_primary.relative_to(root)),
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
        ' reliability closeout summary',
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- 46 activation score: `{payload['rollup']['activation_score']}`",
        f"- 46 checks evaluated: `{payload['rollup']['checks']}`",
        f"- 46 delivery board checklist items: `{payload['rollup']['delivery_board_items']}`",
    ]
    if payload["wins"]:
        lines.append("- Wins:")
        lines.extend([f"  - {w}" for w in payload["wins"]])
    if payload["misses"]:
        lines.append("- Misses:")
        lines.extend([f"  - {m}" for m in payload["misses"]])
    return "\n".join(lines)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _emit_pack(root: Path, payload: dict[str, Any], pack_dir: Path) -> None:
    target = root / pack_dir
    target.mkdir(parents=True, exist_ok=True)
    _write(target / "reliability-closeout-summary-47.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "reliability-closeout-summary-47.md", _render_text(payload) + "\n")
    _write(
        target / "reliability-plan-47.md",
        '#  Reliability Plan\n\n- Objective: close  with measurable reliability and quality gains.\n',
    )
    _write(
        target / "incident-map-47.csv",
        "stream,owner,backup,publish_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "reliability-floor,qa-lead,platform-owner,2026-03-15T10:00:00Z,docs/integrations-reliability-closeout.md,python -m sdetkit reliability-closeout --format json --strict,failed-checks:0,reliability-drift\n",
    )
    _write(
        target / "reliability-kpi-scorecard-47.json",
        json.dumps(
            {
                "kpis": [
                    {
                        "id": "strict_pass",
                        "baseline": 1,
                        "current": int(payload["summary"]["strict_pass"]),
                        "delta": int(payload["summary"]["strict_pass"]) - 1,
                        "confidence": "high",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        target / "execution-log-47.md",
        '#  Execution Log\n\n- [ ] 2026-03-15: Record misses, wins, and  execution priorities.\n',
    )
    _write(
        target / "delivery-board-47.md",
        '#  Delivery Board\n\n' + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "validation-commands-47.md",
        '#  Validation Commands\n\n```bash\n' + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    evidence_path = root / evidence_dir
    evidence_path.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = []
    for index, command in enumerate(_EXECUTION_COMMANDS, start=1):
        argv = shlex.split(command)
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        proc = subprocess.run(argv, cwd=root, text=True, capture_output=True, check=False)
        event = {
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        events.append(event)
        _write(evidence_path / f"command-{index:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        evidence_path / "reliability-execution-summary-47.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reliability closeout checks")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--ensure-doc", action="store_true")
    return parser


def build_reliability_closeout_summary_impl(root: Path) -> dict[str, Any]:
    'Compatibility alias for legacy -based builder name.'
    return build_reliability_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.ensure_doc:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DEFAULT_PAGE_TEMPLATE)

    payload = build_reliability_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/reliability-closeout-pack-47/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
