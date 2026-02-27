from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day67-integration-expansion3-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY66_SUMMARY_PATH = "docs/artifacts/day66-integration-expansion2-closeout-pack/day66-integration-expansion2-closeout-summary.json"
_DAY66_BOARD_PATH = (
    "docs/artifacts/day66-integration-expansion2-closeout-pack/day66-delivery-board.md"
)
_JENKINS_PATH = ".jenkins.day67-advanced-reference.Jenkinsfile"
_SECTION_HEADER = "# Day 67 — Integration expansion #3 closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 67 matters",
    "## Required inputs (Day 66)",
    "## Day 67 command lane",
    "## Integration expansion contract",
    "## Integration quality checklist",
    "## Day 67 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day67-integration-expansion3-closeout --format json --strict",
    "python -m sdetkit day67-integration-expansion3-closeout --emit-pack-dir docs/artifacts/day67-integration-expansion3-closeout-pack --format json --strict",
    "python -m sdetkit day67-integration-expansion3-closeout --execute --evidence-dir docs/artifacts/day67-integration-expansion3-closeout-pack/evidence --format json --strict",
    "python scripts/check_day67_integration_expansion3_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day67-integration-expansion3-closeout --format json --strict",
    "python -m sdetkit day67-integration-expansion3-closeout --emit-pack-dir docs/artifacts/day67-integration-expansion3-closeout-pack --format json --strict",
    "python scripts/check_day67_integration_expansion3_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 67 advanced Jenkins rollout and signoff.",
    "The Day 67 lane references Day 66 integration expansion outputs, governance decisions, and KPI continuity signals.",
    "Every Day 67 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 67 closeout records Jenkins pipeline stages, matrix controls, shared library strategy, and Day 68 integration priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes Jenkins stages + post conditions, matrix or parallel fan-out, and rollback trigger",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures pipeline pass-rate, median runtime, cache efficiency, confidence, and recovery owner",
    "- [ ] Artifact pack includes integration brief, Jenkins blueprint, matrix plan, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 67 integration brief committed",
    "- [ ] Day 67 advanced Jenkins pipeline blueprint published",
    "- [ ] Day 67 matrix and cache strategy exported",
    "- [ ] Day 67 KPI scorecard snapshot exported",
    "- [ ] Day 68 integration expansion priorities drafted from Day 67 learnings",
]
_REQUIRED_JENKINS_LINES = [
    "pipeline {",
    "agent any",
    "stages {",
    "matrix {",
    "post {",
    "parallel",
]

_DAY67_DEFAULT_PAGE = """# Day 67 — Integration expansion #3 closeout lane

Day 67 closes with a major integration upgrade that converts Day 66 integration outputs into an advanced Jenkins reference pipeline.

## Why Day 67 matters

- Converts Day 66 governance outputs into reusable Jenkins implementation patterns.
- Protects integration outcomes with strict contract coverage, runnable commands, and rollback safety.
- Creates a deterministic handoff from Day 67 integration expansion to Day 68 integration expansion #4.

## Required inputs (Day 66)

- `docs/artifacts/day66-integration-expansion2-closeout-pack/day66-integration-expansion2-closeout-summary.json`
- `docs/artifacts/day66-integration-expansion2-closeout-pack/day66-delivery-board.md`
- `.jenkins.day67-advanced-reference.Jenkinsfile`

## Day 67 command lane

```bash
python -m sdetkit day67-integration-expansion3-closeout --format json --strict
python -m sdetkit day67-integration-expansion3-closeout --emit-pack-dir docs/artifacts/day67-integration-expansion3-closeout-pack --format json --strict
python -m sdetkit day67-integration-expansion3-closeout --execute --evidence-dir docs/artifacts/day67-integration-expansion3-closeout-pack/evidence --format json --strict
python scripts/check_day67_integration_expansion3_closeout_contract.py
```

## Integration expansion contract

- Single owner + backup reviewer are assigned for Day 67 advanced Jenkins rollout and signoff.
- The Day 67 lane references Day 66 integration expansion outputs, governance decisions, and KPI continuity signals.
- Every Day 67 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 67 closeout records Jenkins pipeline stages, matrix controls, shared library strategy, and Day 68 integration priorities.

## Integration quality checklist

- [ ] Includes Jenkins stages + post conditions, matrix or parallel fan-out, and rollback trigger
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures pipeline pass-rate, median runtime, cache efficiency, confidence, and recovery owner
- [ ] Artifact pack includes integration brief, Jenkins blueprint, matrix plan, KPI scorecard, and execution log

## Day 67 delivery board

- [ ] Day 67 integration brief committed
- [ ] Day 67 advanced Jenkins pipeline blueprint published
- [ ] Day 67 matrix and cache strategy exported
- [ ] Day 67 KPI scorecard snapshot exported
- [ ] Day 68 integration expansion priorities drafted from Day 67 learnings

## Scoring model

Day 67 weighted score (0-100):

- Contract + command lane completeness: 25 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 66 continuity and strict baseline carryover: 30 points.
- Jenkins reference quality + guardrails: 25 points.
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


def _load_day66(path: Path) -> tuple[int, bool, int]:
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


def build_day67_integration_expansion3_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    jenkins_text = _read(root / _JENKINS_PATH)

    day66_summary = root / _DAY66_SUMMARY_PATH
    day66_board = root / _DAY66_BOARD_PATH
    day66_score, day66_strict, day66_check_count = _load_day66(day66_summary)
    board_count, board_has_day66 = _count_board_items(day66_board, "Day 66")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_jenkins_lines = [x for x in _REQUIRED_JENKINS_LINES if x not in jenkins_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day67_command",
            "weight": 7,
            "passed": ("day67-integration-expansion3-closeout" in readme_text),
            "evidence": "README day67 command lane",
        },
        {
            "check_id": "docs_index_day67_links",
            "weight": 8,
            "passed": (
                "day-67-big-upgrade-report.md" in docs_index_text
                and "integrations-day67-integration-expansion3-closeout.md" in docs_index_text
            ),
            "evidence": "day-67-big-upgrade-report.md + integrations-day67-integration-expansion3-closeout.md",
        },
        {
            "check_id": "top10_day67_alignment",
            "weight": 5,
            "passed": ("Day 67" in top10_text and "Day 68" in top10_text),
            "evidence": "Day 67 + Day 68 strategy chain",
        },
        {
            "check_id": "day66_summary_present",
            "weight": 10,
            "passed": day66_summary.exists(),
            "evidence": str(day66_summary),
        },
        {
            "check_id": "day66_delivery_board_present",
            "weight": 7,
            "passed": day66_board.exists(),
            "evidence": str(day66_board),
        },
        {
            "check_id": "day66_quality_floor",
            "weight": 13,
            "passed": day66_strict and day66_score >= 95,
            "evidence": {
                "day66_score": day66_score,
                "strict_pass": day66_strict,
                "day66_checks": day66_check_count,
            },
        },
        {
            "check_id": "day66_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day66,
            "evidence": {"board_items": board_count, "contains_day66": board_has_day66},
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
            "check_id": "jenkins_reference_present",
            "weight": 10,
            "passed": not missing_jenkins_lines,
            "evidence": missing_jenkins_lines or _JENKINS_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day66_summary.exists() or not day66_board.exists():
        critical_failures.append("day66_handoff_inputs")
    if not day66_strict:
        critical_failures.append("day66_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day66_strict:
        wins.append(f"Day 66 continuity is strict-pass with activation score={day66_score}.")
    else:
        misses.append("Day 66 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 66 closeout command and restore strict baseline before Day 67 lock."
        )

    if board_count >= 5 and board_has_day66:
        wins.append(
            f"Day 66 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 66 delivery board integrity is incomplete (needs >=5 items and Day 66 anchors)."
        )
        handoff_actions.append("Repair Day 66 delivery board entries to include Day 66 anchors.")

    if not missing_jenkins_lines:
        wins.append(
            "Day 67 Jenkins reference pipeline is available for integration expansion execution."
        )
    else:
        misses.append("Day 67 Jenkins reference pipeline is missing required controls.")
        handoff_actions.append(
            "Update .jenkins.day67-advanced-reference.Jenkinsfile to restore required controls."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 67 integration expansion #3 closeout lane is fully complete and ready for Day 68 integration expansion #4."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day67-integration-expansion3-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day66_summary": str(day66_summary.relative_to(root))
            if day66_summary.exists()
            else str(day66_summary),
            "day66_delivery_board": str(day66_board.relative_to(root))
            if day66_board.exists()
            else str(day66_board),
            "jenkins_reference": _JENKINS_PATH,
        },
        "checks": checks,
        "rollup": {
            "day66_activation_score": day66_score,
            "day66_checks": day66_check_count,
            "day66_delivery_board_items": board_count,
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
        "Day 67 integration expansion #3 closeout summary",
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
        target / "day67-integration-expansion3-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(
        target / "day67-integration-expansion3-closeout-summary.md", _render_text(payload) + "\n"
    )
    _write(target / "day67-integration-brief.md", "# Day 67 integration brief\n")
    _write(target / "day67-jenkins-blueprint.md", "# Day 67 Jenkins blueprint\n")
    _write(target / "day67-matrix-plan.json", json.dumps({"matrix": []}, indent=2) + "\n")
    _write(target / "day67-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day67-execution-log.md", "# Day 67 execution log\n")
    _write(
        target / "day67-delivery-board.md",
        "\n".join(["# Day 67 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day67-validation-commands.md",
        "# Day 67 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    events: list[dict[str, Any]] = []
    out_dir = evidence_dir if evidence_dir.is_absolute() else root / evidence_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, command in enumerate(_EXECUTION_COMMANDS, start=1):
        result = subprocess.run(shlex.split(command), cwd=root, capture_output=True, text=True)
        event = {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        events.append(event)
        _write(out_dir / f"command-{idx:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        out_dir / "day67-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 67 integration expansion #3 closeout checks")
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
        _write(root / _PAGE_PATH, _DAY67_DEFAULT_PAGE)

    payload = build_day67_integration_expansion3_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day67-integration-expansion3-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
