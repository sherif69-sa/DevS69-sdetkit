from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-contributor-recognition-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY75_SUMMARY_PATH = (
    "docs/artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-closeout-summary.json"
)
_DAY75_BOARD_PATH = (
    "docs/artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-delivery-board.md"
)
_PLAN_PATH = "docs/roadmap/plans/contributor-recognition-plan.json"
_SECTION_HEADER = "#  — Contributor recognition closeout lane"
_REQUIRED_SECTIONS = [
    "## Why  matters",
    "## Required inputs ()",
    "##  command lane",
    "## Contributor recognition contract",
    "## Recognition quality checklist",
    "##  delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit contributor-recognition-closeout --format json --strict",
    "python -m sdetkit contributor-recognition-closeout --emit-pack-dir docs/artifacts/contributor-recognition-closeout-pack --format json --strict",
    "python -m sdetkit contributor-recognition-closeout --execute --evidence-dir docs/artifacts/contributor-recognition-closeout-pack/evidence --format json --strict",
    "python scripts/check_contributor_recognition_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit contributor-recognition-closeout --format json --strict",
    "python -m sdetkit contributor-recognition-closeout --emit-pack-dir docs/artifacts/contributor-recognition-closeout-pack --format json --strict",
    "python scripts/check_contributor_recognition_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for  contributor recognition execution and signoff.",
    "The  lane references  outcomes, controls, and KPI continuity signals.",
    "Every  section includes contributor CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    " closeout records recognition outcomes, confidence notes, and  scale priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes contributor baseline, recognition cadence, and stakeholder assumptions",
    "- [ ] Every recognition lane row has owner, publish window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures recognition score delta, trust carryover delta, confidence, and rollback owner",
    "- [ ] Artifact pack includes integration brief, recognition plan, credits ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ]  integration brief committed",
    "- [ ]  contributor recognition plan committed",
    "- [ ]  recognition credits ledger exported",
    "- [ ]  recognition KPI scorecard snapshot exported",
    "- [ ]  scale priorities drafted from  learnings",
]
_REQUIRED_DATA_KEYS = [
    '"plan_id"',
    '"contributors"',
    '"recognition_tracks"',
    '"baseline"',
    '"target"',
    '"owner"',
]

_DEFAULT_PAGE_TEMPLATE = "#  — Contributor recognition closeout lane\n\n closes with a major upgrade that converts  trust refresh outcomes into a contributor-recognition execution pack.\n\n## Why  matters\n\n- Turns  trust outcomes into contributor-facing recognition proof across docs, governance, and release channels.\n- Protects launch quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.\n- Creates a deterministic handoff from  contributor recognition into  scale priorities.\n\n## Required inputs ()\n\n- `docs/artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-closeout-summary.json`\n- `docs/artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-delivery-board.md`\n- `docs/roadmap/plans/contributor-recognition-plan.json`\n\n##  command lane\n\n```bash\npython -m sdetkit contributor-recognition-closeout --format json --strict\npython -m sdetkit contributor-recognition-closeout --emit-pack-dir docs/artifacts/contributor-recognition-closeout-pack --format json --strict\npython -m sdetkit contributor-recognition-closeout --execute --evidence-dir docs/artifacts/contributor-recognition-closeout-pack/evidence --format json --strict\npython scripts/check_contributor_recognition_closeout_contract.py\n```\n\n## Contributor recognition contract\n\n- Single owner + backup reviewer are assigned for  contributor recognition execution and signoff.\n- The  lane references  outcomes, controls, and KPI continuity signals.\n- Every  section includes contributor CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n-  closeout records recognition outcomes, confidence notes, and  scale priorities.\n\n## Recognition quality checklist\n\n- [ ] Includes contributor baseline, recognition cadence, and stakeholder assumptions\n- [ ] Every recognition lane row has owner, publish window, KPI threshold, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures recognition score delta, trust carryover delta, confidence, and rollback owner\n- [ ] Artifact pack includes integration brief, recognition plan, credits ledger, KPI scorecard, and execution log\n\n##  delivery board\n\n- [ ]  integration brief committed\n- [ ]  contributor recognition plan committed\n- [ ]  recognition credits ledger exported\n- [ ]  recognition KPI scorecard snapshot exported\n- [ ]  scale priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Contract + command lane integrity (35)\n-  continuity baseline quality (35)\n- Recognition evidence data + delivery board completeness (30)\n\nStrict pass requires score >= 95 and zero critical failures.\n"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_trust_assets_refresh(summary_path: Path) -> tuple[int, bool, int]:
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


def build_contributor_recognition_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    plan_text = _read(root / _PLAN_PATH)

    trust_assets_refresh_summary = root / _DAY75_SUMMARY_PATH
    trust_assets_refresh_board = root / _DAY75_BOARD_PATH
    trust_assets_refresh_score, trust_assets_refresh_strict, trust_assets_refresh_check_count = (
        _load_trust_assets_refresh(trust_assets_refresh_summary)
    )
    board_count, board_has_trust_assets_refresh = _count_board_items(trust_assets_refresh_board, "")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_plan_keys = [x for x in _REQUIRED_DATA_KEYS if x not in plan_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_command_lane",
            "weight": 7,
            "passed": (
                "contributor-recognition-closeout" in readme_text
                or "contributor-recognition-closeout" in readme_text
            ),
            "evidence": "README contributor-recognition-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-76-big-upgrade-report.md" in docs_index_text
                and "integrations-contributor-recognition-closeout.md" in docs_index_text
            ),
            "evidence": "impact-76-big-upgrade-report.md + integrations-contributor-recognition-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ("" in top10_text and "" in top10_text),
            "evidence": " +  strategy chain",
        },
        {
            "check_id": "trust_assets_refresh_summary_present",
            "weight": 10,
            "passed": trust_assets_refresh_summary.exists(),
            "evidence": str(trust_assets_refresh_summary),
        },
        {
            "check_id": "trust_assets_refresh_delivery_board_present",
            "weight": 7,
            "passed": trust_assets_refresh_board.exists(),
            "evidence": str(trust_assets_refresh_board),
        },
        {
            "check_id": "trust_assets_refresh_quality_floor",
            "weight": 13,
            "passed": trust_assets_refresh_strict and trust_assets_refresh_score >= 95,
            "evidence": {
                "trust_assets_refresh_score": trust_assets_refresh_score,
                "strict_pass": trust_assets_refresh_strict,
                "trust_assets_refresh_checks": trust_assets_refresh_check_count,
            },
        },
        {
            "check_id": "trust_assets_refresh_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_trust_assets_refresh,
            "evidence": {
                "board_items": board_count,
                "contains_trust_assets_refresh": board_has_trust_assets_refresh,
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
            "check_id": "recognition_plan_data_present",
            "weight": 10,
            "passed": not missing_plan_keys,
            "evidence": missing_plan_keys or _PLAN_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not trust_assets_refresh_summary.exists() or not trust_assets_refresh_board.exists():
        critical_failures.append("trust_assets_refresh_handoff_inputs")
    if not trust_assets_refresh_strict:
        critical_failures.append("trust_assets_refresh_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if trust_assets_refresh_strict:
        wins.append(
            f"75 continuity is strict-pass with activation score={trust_assets_refresh_score}."
        )
    else:
        misses.append(" strict continuity signal is missing.")
        handoff_actions.append("Re-run  closeout command and restore strict baseline before  lock.")

    if board_count >= 5 and board_has_trust_assets_refresh:
        wins.append(f"75 delivery board integrity validated with {board_count} checklist items.")
    else:
        misses.append(" delivery board integrity is incomplete (needs >=5 items and  anchors).")
        handoff_actions.append("Repair  delivery board entries to include  anchors.")

    if not missing_plan_keys:
        wins.append(" contributor recognition dataset is available for launch execution.")
    else:
        misses.append(" contributor recognition dataset is missing required keys.")
        handoff_actions.append(
            "Update docs/roadmap/plans/contributor-recognition-plan.json to restore required keys."
        )

    if not failed and not critical_failures:
        wins.append(
            " contributor recognition closeout lane is fully complete and ready for  scale priorities."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "contributor-recognition-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "trust_assets_refresh_summary": str(trust_assets_refresh_summary.relative_to(root))
            if trust_assets_refresh_summary.exists()
            else str(trust_assets_refresh_summary),
            "trust_assets_refresh_delivery_board": str(trust_assets_refresh_board.relative_to(root))
            if trust_assets_refresh_board.exists()
            else str(trust_assets_refresh_board),
            "recognition_plan": _PLAN_PATH,
        },
        "checks": checks,
        "rollup": {
            "trust_assets_refresh_activation_score": trust_assets_refresh_score,
            "trust_assets_refresh_checks": trust_assets_refresh_check_count,
            "trust_assets_refresh_delivery_board_items": board_count,
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
        "Contributor Recognition Closeout summary",
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
        target / "contributor-recognition-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "contributor-recognition-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "contributor-recognition-integration-brief.md", "#  integration brief\n")
    _write(target / "contributor-recognition-plan.md", "#  contributor recognition plan\n")
    _write(
        target / "contributor-recognition-credits-ledger.json",
        json.dumps({"credits": []}, indent=2) + "\n",
    )
    _write(
        target / "contributor-recognition-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(target / "contributor-recognition-execution-log.md", "#  execution log\n")
    _write(
        target / "contributor-recognition-delivery-board.md",
        "\n".join(["#  delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "contributor-recognition-validation-commands.md",
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
        out_dir / "contributor-recognition-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_contributor_recognition_closeout_summary_impl(root: Path) -> dict[str, Any]:
    "Compatibility alias for legacy -based builder name."
    return build_contributor_recognition_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Contributor Recognition Closeout checks")
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

    payload = build_contributor_recognition_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/contributor-recognition-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
