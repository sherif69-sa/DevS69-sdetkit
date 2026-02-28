from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day68-integration-expansion4-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY67_SUMMARY_PATH = "docs/artifacts/day67-integration-expansion3-closeout-pack/day67-integration-expansion3-closeout-summary.json"
_DAY67_BOARD_PATH = (
    "docs/artifacts/day67-integration-expansion3-closeout-pack/day67-delivery-board.md"
)
_REFERENCE_PATH = ".tekton.day68-self-hosted-reference.yaml"
_SECTION_HEADER = "# Day 68 \u2014 Integration expansion #4 closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 68 matters",
    "## Required inputs (Day 67)",
    "## Day 68 command lane",
    "## Integration expansion contract",
    "## Integration quality checklist",
    "## Day 68 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day68-integration-expansion4-closeout --format json --strict",
    "python -m sdetkit day68-integration-expansion4-closeout --emit-pack-dir docs/artifacts/day68-integration-expansion4-closeout-pack --format json --strict",
    "python -m sdetkit day68-integration-expansion4-closeout --execute --evidence-dir docs/artifacts/day68-integration-expansion4-closeout-pack/evidence --format json --strict",
    "python scripts/check_day68_integration_expansion4_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day68-integration-expansion4-closeout --format json --strict",
    "python -m sdetkit day68-integration-expansion4-closeout --emit-pack-dir docs/artifacts/day68-integration-expansion4-closeout-pack --format json --strict",
    "python scripts/check_day68_integration_expansion4_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 68 self-hosted enterprise rollout and signoff.",
    "The Day 68 lane references Day 67 integration expansion outputs, governance decisions, and KPI continuity signals.",
    "Every Day 68 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 68 closeout records self-hosted pipeline stages, identity controls, runner policy strategy, and Day 69 case-study prep priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes self-hosted stages + policy conditions, queue/parallel fan-out, and rollback trigger",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures pipeline pass-rate, median runtime, queue saturation, confidence, and recovery owner",
    "- [ ] Artifact pack includes integration brief, self-hosted blueprint, policy plan, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 68 integration brief committed",
    "- [ ] Day 68 self-hosted enterprise pipeline blueprint published",
    "- [ ] Day 68 identity and runner policy strategy exported",
    "- [ ] Day 68 KPI scorecard snapshot exported",
    "- [ ] Day 69 case-study prep priorities drafted from Day 68 learnings",
]
_REQUIRED_REFERENCE_LINES = [
    "apiVersion: tekton.dev/v1",
    "kind: Pipeline",
    "serviceAccountName:",
    "workspaces:",
    "finally:",
    "when:",
]

_DAY68_DEFAULT_PAGE = """# Day 68 \u2014 Integration expansion #4 closeout lane

Day 68 closes with a major integration upgrade that converts Day 67 outputs into a self-hosted enterprise Tekton reference.

## Why Day 68 matters

- Converts Day 67 governance outputs into reusable self-hosted implementation patterns.
- Protects integration outcomes with strict contract coverage, runnable commands, and rollback safety.
- Creates a deterministic handoff from Day 68 integration expansion to Day 69 case-study prep #1.

## Required inputs (Day 67)

- `docs/artifacts/day67-integration-expansion3-closeout-pack/day67-integration-expansion3-closeout-summary.json`
- `docs/artifacts/day67-integration-expansion3-closeout-pack/day67-delivery-board.md`
- `.tekton.day68-self-hosted-reference.yaml`

## Day 68 command lane

```bash
python -m sdetkit day68-integration-expansion4-closeout --format json --strict
python -m sdetkit day68-integration-expansion4-closeout --emit-pack-dir docs/artifacts/day68-integration-expansion4-closeout-pack --format json --strict
python -m sdetkit day68-integration-expansion4-closeout --execute --evidence-dir docs/artifacts/day68-integration-expansion4-closeout-pack/evidence --format json --strict
python scripts/check_day68_integration_expansion4_closeout_contract.py
```

## Integration expansion contract

- Single owner + backup reviewer are assigned for Day 68 self-hosted enterprise rollout and signoff.
- The Day 68 lane references Day 67 integration expansion outputs, governance decisions, and KPI continuity signals.
- Every Day 68 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 68 closeout records self-hosted pipeline stages, identity controls, runner policy strategy, and Day 69 case-study prep priorities.

## Integration quality checklist

- [ ] Includes self-hosted stages + policy conditions, queue/parallel fan-out, and rollback trigger
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures pipeline pass-rate, median runtime, queue saturation, confidence, and recovery owner
- [ ] Artifact pack includes integration brief, self-hosted blueprint, policy plan, KPI scorecard, and execution log

## Day 68 delivery board

- [ ] Day 68 integration brief committed
- [ ] Day 68 self-hosted enterprise pipeline blueprint published
- [ ] Day 68 identity and runner policy strategy exported
- [ ] Day 68 KPI scorecard snapshot exported
- [ ] Day 69 case-study prep priorities drafted from Day 68 learnings

## Scoring model

Day 68 weighted score (0-100):

- Contract + command lane completeness: 25 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 67 continuity and strict baseline carryover: 30 points.
- Self-hosted reference quality + guardrails: 25 points.
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


def _load_day67(path: Path) -> tuple[int, bool, int]:
    payload_obj = _load_json(path)
    if not isinstance(payload_obj, dict):
        return 0, False, 0
    summary_obj = payload_obj.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    score = int(summary.get("activation_score", 0))
    strict = bool(summary.get("strict_pass", False))
    checks_obj = payload_obj.get("checks")
    checks = checks_obj if isinstance(checks_obj, list) else []
    return score, strict, len(checks)


def _count_board_items(path: Path, needle: str) -> tuple[int, bool]:
    text = _read(path)
    lines = [ln.strip() for ln in text.splitlines()]
    checks = [ln for ln in lines if ln.startswith("- [")]
    return len(checks), (needle in text)


def build_day68_integration_expansion4_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    reference_text = _read(root / _REFERENCE_PATH)

    day67_summary = root / _DAY67_SUMMARY_PATH
    day67_board = root / _DAY67_BOARD_PATH
    day67_score, day67_strict, day67_check_count = _load_day67(day67_summary)
    board_count, board_has_day67 = _count_board_items(day67_board, "Day 67")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_reference_lines = [x for x in _REQUIRED_REFERENCE_LINES if x not in reference_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day68_command",
            "weight": 7,
            "passed": ("day68-integration-expansion4-closeout" in readme_text),
            "evidence": "README day68 command lane",
        },
        {
            "check_id": "docs_index_day68_links",
            "weight": 8,
            "passed": (
                "day-68-big-upgrade-report.md" in docs_index_text
                and "integrations-day68-integration-expansion4-closeout.md" in docs_index_text
            ),
            "evidence": "day-68-big-upgrade-report.md + integrations-day68-integration-expansion4-closeout.md",
        },
        {
            "check_id": "top10_day68_alignment",
            "weight": 5,
            "passed": ("Day 68" in top10_text and "Day 69" in top10_text),
            "evidence": "Day 68 + Day 69 strategy chain",
        },
        {
            "check_id": "day67_summary_present",
            "weight": 10,
            "passed": day67_summary.exists(),
            "evidence": str(day67_summary),
        },
        {
            "check_id": "day67_delivery_board_present",
            "weight": 7,
            "passed": day67_board.exists(),
            "evidence": str(day67_board),
        },
        {
            "check_id": "day67_quality_floor",
            "weight": 13,
            "passed": day67_strict and day67_score >= 95,
            "evidence": {
                "day67_score": day67_score,
                "strict_pass": day67_strict,
                "day67_checks": day67_check_count,
            },
        },
        {
            "check_id": "day67_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day67,
            "evidence": {"board_items": board_count, "contains_day67": board_has_day67},
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
            "check_id": "self_hosted_reference_present",
            "weight": 10,
            "passed": not missing_reference_lines,
            "evidence": missing_reference_lines or _REFERENCE_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day67_summary.exists() or not day67_board.exists():
        critical_failures.append("day67_handoff_inputs")
    if not day67_strict:
        critical_failures.append("day67_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day67_strict:
        wins.append(f"Day 67 continuity is strict-pass with activation score={day67_score}.")
    else:
        misses.append("Day 67 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 67 closeout command and restore strict baseline before Day 68 lock."
        )

    if board_count >= 5 and board_has_day67:
        wins.append(
            f"Day 67 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 67 delivery board integrity is incomplete (needs >=5 items and Day 67 anchors)."
        )
        handoff_actions.append("Repair Day 67 delivery board entries to include Day 67 anchors.")

    if not missing_reference_lines:
        wins.append(
            "Day 68 self-hosted reference pipeline is available for integration expansion execution."
        )
    else:
        misses.append("Day 68 self-hosted reference pipeline is missing required controls.")
        handoff_actions.append(
            "Update .tekton.day68-self-hosted-reference.yaml to restore required controls."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 68 integration expansion #4 closeout lane is fully complete and ready for Day 69 case-study prep #1."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day68-integration-expansion4-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day67_summary": str(day67_summary.relative_to(root))
            if day67_summary.exists()
            else str(day67_summary),
            "day67_delivery_board": str(day67_board.relative_to(root))
            if day67_board.exists()
            else str(day67_board),
            "self_hosted_reference": _REFERENCE_PATH,
        },
        "checks": checks,
        "rollup": {
            "day67_activation_score": day67_score,
            "day67_checks": day67_check_count,
            "day67_delivery_board_items": board_count,
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
        "Day 68 integration expansion #4 closeout summary",
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
        target / "day68-integration-expansion4-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(
        target / "day68-integration-expansion4-closeout-summary.md", _render_text(payload) + "\n"
    )
    _write(target / "day68-integration-brief.md", "# Day 68 integration brief\n")
    _write(target / "day68-self-hosted-blueprint.md", "# Day 68 self-hosted blueprint\n")
    _write(target / "day68-policy-plan.json", json.dumps({"policy_controls": []}, indent=2) + "\n")
    _write(target / "day68-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day68-execution-log.md", "# Day 68 execution log\n")
    _write(
        target / "day68-delivery-board.md",
        "\n".join(["# Day 68 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day68-validation-commands.md",
        "# Day 68 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day68-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 68 integration expansion #4 closeout checks")
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
        _write(root / _PAGE_PATH, _DAY68_DEFAULT_PAGE)

    payload = build_day68_integration_expansion4_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day68-integration-expansion4-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
