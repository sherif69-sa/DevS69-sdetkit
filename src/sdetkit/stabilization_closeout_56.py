from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-stabilization-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY55_SUMMARY_PATH = "docs/artifacts/contributor-activation-closeout-pack/contributor-activation-closeout-summary.json"
_DAY55_BOARD_PATH = (
    "docs/artifacts/contributor-activation-closeout-pack/contributor-activation-delivery-board.md"
)
_SECTION_HEADER = "# \u2014 Stabilization closeout lane"
_REQUIRED_SECTIONS = [
    "## Why matters",
    "## Required inputs ()",
    "## command lane",
    "## Stabilization contract",
    "## Stabilization quality checklist",
    "## delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit stabilization-closeout --format json --strict",
    "python -m sdetkit stabilization-closeout --emit-pack-dir docs/artifacts/stabilization-closeout-pack --format json --strict",
    "python -m sdetkit stabilization-closeout --execute --evidence-dir docs/artifacts/stabilization-closeout-pack/evidence --format json --strict",
    "python scripts/check_stabilization_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit stabilization-closeout --format json --strict",
    "python -m sdetkit stabilization-closeout --emit-pack-dir docs/artifacts/stabilization-closeout-pack --format json --strict",
    "python scripts/check_stabilization_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for stabilization execution and KPI recovery.",
    "The lane references contributor activation outcomes and unresolved risks.",
    "Every section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "closeout records stabilization outcomes and deep-audit priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes bottleneck digest, remediation experiments, and rollback strategy",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes stabilization brief, risk ledger, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] stabilization brief committed",
    "- [ ] stabilization plan reviewed with owner + backup",
    "- [ ] risk ledger exported",
    "- [ ] KPI scorecard snapshot exported",
    "- [ ] deep-audit priorities drafted from learnings",
]

_DEFAULT_PAGE_TEMPLATE = """# \u2014 Stabilization closeout lane

closes with a major stabilization upgrade that turns contributor-activation outcomes into deterministic KPI recovery and follow-through.

## Why matters

- Converts contributor outcomes into repeatable stabilization loops.
- Protects quality with ownership, command proof, and KPI rollback guardrails.
- Produces a deterministic handoff from closeout into deep audit planning.

## Required inputs ()

- `docs/artifacts/contributor-activation-closeout-pack/contributor-activation-closeout-summary.json`
- `docs/artifacts/contributor-activation-closeout-pack/contributor-activation-delivery-board.md`

## command lane

```bash
python -m sdetkit stabilization-closeout --format json --strict
python -m sdetkit stabilization-closeout --emit-pack-dir docs/artifacts/stabilization-closeout-pack --format json --strict
python -m sdetkit stabilization-closeout --execute --evidence-dir docs/artifacts/stabilization-closeout-pack/evidence --format json --strict
python scripts/check_stabilization_closeout_contract.py
```

## Stabilization contract

- Single owner + backup reviewer are assigned for stabilization execution and KPI recovery.
- The lane references contributor activation outcomes and unresolved risks.
- Every section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- closeout records stabilization outcomes and deep-audit priorities.

## Stabilization quality checklist

- [ ] Includes bottleneck digest, remediation experiments, and rollback strategy
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes stabilization brief, risk ledger, KPI scorecard, and execution log

## delivery board

- [ ] stabilization brief committed
- [ ] stabilization plan reviewed with owner + backup
- [ ] risk ledger exported
- [ ] KPI scorecard snapshot exported
- [ ] deep-audit priorities drafted from learnings

## Scoring model

weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Contributor-activation continuity and strict baseline carryover: 35 points.
- Stabilization contract lock + delivery board readiness: 15 points.
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


def _load_contributor_activation_summary(path: Path) -> tuple[int, bool, int]:
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


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def _board_stats(path: Path) -> tuple[int, bool]:
    text = _read(path)
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- [")]
    return len(lines), ("" in text)


def build_stabilization_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_path = root / _PAGE_PATH
    page_text = _read(page_path)
    top10_text = _read(root / _TOP10_PATH)

    missing_sections = [
        item for item in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if item not in page_text
    ]
    missing_commands = _contains_all_lines(page_text, _REQUIRED_COMMANDS)
    missing_contract_lines = _contains_all_lines(
        page_text, [f"- {line}" for line in _REQUIRED_CONTRACT_LINES]
    )
    missing_quality_lines = _contains_all_lines(page_text, _REQUIRED_QUALITY_LINES)
    missing_board_items = _contains_all_lines(page_text, _REQUIRED_DELIVERY_BOARD_LINES)

    contributor_activation_summary = root / _DAY55_SUMMARY_PATH
    contributor_activation_board = root / _DAY55_BOARD_PATH
    (
        contributor_activation_score,
        contributor_activation_strict,
        contributor_activation_check_count,
    ) = _load_contributor_activation_summary(contributor_activation_summary)
    board_count, board_has_required = _board_stats(contributor_activation_board)

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
            "passed": "stabilization-closeout" in readme_text,
            "evidence": "README stabilization-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-56-big-upgrade-report.md" in docs_index_text
                and "integrations-stabilization-closeout.md" in docs_index_text
            ),
            "evidence": "impact-56-big-upgrade-report.md + integrations-stabilization-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ("" in top10_text and "" in top10_text),
            "evidence": "+ strategy chain",
        },
        {
            "check_id": "contributor_activation_summary_present",
            "weight": 10,
            "passed": contributor_activation_summary.exists(),
            "evidence": str(contributor_activation_summary),
        },
        {
            "check_id": "contributor_activation_delivery_board_present",
            "weight": 8,
            "passed": contributor_activation_board.exists(),
            "evidence": str(contributor_activation_board),
        },
        {
            "check_id": "contributor_activation_quality_floor",
            "weight": 10,
            "passed": contributor_activation_strict and contributor_activation_score >= 95,
            "evidence": {
                "contributor_activation_score": contributor_activation_score,
                "strict_pass": contributor_activation_strict,
                "contributor_activation_checks": contributor_activation_check_count,
            },
        },
        {
            "check_id": "contributor_activation_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_required,
            "evidence": {
                "board_items": board_count,
                "contains_required": board_has_required,
            },
        },
        {
            "check_id": "stabilization_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "stabilization_quality_checklist_locked",
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
    if not contributor_activation_summary.exists() or not contributor_activation_board.exists():
        critical_failures.append("contributor_activation_handoff_inputs")
    if not contributor_activation_strict:
        critical_failures.append("contributor_activation_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if contributor_activation_strict:
        wins.append(
            f"Contributor-activation continuity is strict-pass with activation score={contributor_activation_score}."
        )
    else:
        misses.append("strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run contributor activation closeout command and restore strict baseline before lock."
        )

    if board_count >= 5 and board_has_required:
        wins.append(
            f"delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "delivery board integrity is incomplete (needs >=5 items and anchors)."
        )
        handoff_actions.append("Repair delivery board entries to include anchors.")

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append("Stabilization contract + quality checklist is fully locked for execution.")
    else:
        misses.append(
            "Stabilization contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "stabilization closeout lane is fully complete and ready for deep audit lane."
        )

    score = int(round(sum(c["weight"] for c in checks if bool(c["passed"]))))
    return {
        "name": "stabilization-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "contributor_activation_summary": str(contributor_activation_summary.relative_to(root))
            if contributor_activation_summary.exists()
            else str(contributor_activation_summary),
            "contributor_activation_delivery_board": str(
                contributor_activation_board.relative_to(root)
            )
            if contributor_activation_board.exists()
            else str(contributor_activation_board),
        },
        "checks": checks,
        "rollup": {
            "contributor_activation_activation_score": contributor_activation_score,
            "contributor_activation_checks": contributor_activation_check_count,
            "contributor_activation_delivery_board_items": board_count,
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
        "Stabilization Closeout summary (legacy: )",
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
    _write(target / "stabilization-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "stabilization-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "stabilization-brief.md", "# stabilization brief\n")
    _write(target / "stabilization-risk-ledger.csv", "risk,owner,mitigation,status\n")
    _write(target / "stabilization-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "stabilization-execution-log.md", "# execution log\n")
    _write(
        target / "stabilization-delivery-board.md",
        "\n".join(["# delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "stabilization-validation-commands.md",
        "# validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "stabilization-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_stabilization_closeout_summary_impl(root: Path) -> dict[str, Any]:
    """Compatibility alias for legacy builder name."""
    return build_stabilization_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stabilization Closeout checks")
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

    payload = build_stabilization_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/stabilization-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
