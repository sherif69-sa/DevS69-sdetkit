from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day66-integration-expansion2-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY65_SUMMARY_PATH = "docs/artifacts/day65-weekly-review-closeout-pack/day65-weekly-review-closeout-summary.json"
_DAY65_BOARD_PATH = "docs/artifacts/day65-weekly-review-closeout-pack/day65-delivery-board.md"
_GITLAB_PATH = ".gitlab-ci.day66-advanced-reference.yml"
_SECTION_HEADER = "# Day 66 — Integration expansion #2 closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 66 matters",
    "## Required inputs (Day 65)",
    "## Day 66 command lane",
    "## Integration expansion contract",
    "## Integration quality checklist",
    "## Day 66 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day66-integration-expansion2-closeout --format json --strict",
    "python -m sdetkit day66-integration-expansion2-closeout --emit-pack-dir docs/artifacts/day66-integration-expansion2-closeout-pack --format json --strict",
    "python -m sdetkit day66-integration-expansion2-closeout --execute --evidence-dir docs/artifacts/day66-integration-expansion2-closeout-pack/evidence --format json --strict",
    "python scripts/check_day66_integration_expansion2_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day66-integration-expansion2-closeout --format json --strict",
    "python -m sdetkit day66-integration-expansion2-closeout --emit-pack-dir docs/artifacts/day66-integration-expansion2-closeout-pack --format json --strict",
    "python scripts/check_day66_integration_expansion2_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 66 advanced GitLab CI rollout and signoff.",
    "The Day 66 lane references Day 65 weekly review outputs, governance decisions, and KPI continuity signals.",
    "Every Day 66 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    "Day 66 closeout records GitLab pipeline stages, parallel matrix controls, cache strategy, and Day 67 integration priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes GitLab stages + rules path, matrix or parallel fan-out, and rollback trigger",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures pipeline pass-rate, median runtime, cache efficiency, confidence, and recovery owner",
    "- [ ] Artifact pack includes integration brief, pipeline blueprint, matrix plan, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 66 integration brief committed",
    "- [ ] Day 66 advanced GitLab pipeline blueprint published",
    "- [ ] Day 66 matrix and cache strategy exported",
    "- [ ] Day 66 KPI scorecard snapshot exported",
    "- [ ] Day 67 integration expansion priorities drafted from Day 66 learnings",
]
_REQUIRED_GITLAB_LINES = [
    "stages:",
    "workflow:",
    "rules:",
    "parallel:",
    "matrix:",
    "cache:",
]

_DAY66_DEFAULT_PAGE = """# Day 66 — Integration expansion #2 closeout lane

Day 66 closes with a major integration upgrade that converts Day 65 weekly review outcomes into an advanced GitLab CI reference pipeline.

## Why Day 66 matters

- Converts Day 65 governance outputs into reusable GitLab CI implementation patterns.
- Protects integration outcomes with strict contract coverage, runnable commands, and rollback safety.
- Creates a deterministic handoff from Day 66 integration expansion to Day 67 integration expansion #3.

## Required inputs (Day 65)

- `docs/artifacts/day65-weekly-review-closeout-pack/day65-weekly-review-closeout-summary.json`
- `docs/artifacts/day65-weekly-review-closeout-pack/day65-delivery-board.md`
- `.gitlab-ci.day66-advanced-reference.yml`

## Day 66 command lane

```bash
python -m sdetkit day66-integration-expansion2-closeout --format json --strict
python -m sdetkit day66-integration-expansion2-closeout --emit-pack-dir docs/artifacts/day66-integration-expansion2-closeout-pack --format json --strict
python -m sdetkit day66-integration-expansion2-closeout --execute --evidence-dir docs/artifacts/day66-integration-expansion2-closeout-pack/evidence --format json --strict
python scripts/check_day66_integration_expansion2_closeout_contract.py
```

## Integration expansion contract

- Single owner + backup reviewer are assigned for Day 66 advanced GitLab CI rollout and signoff.
- The Day 66 lane references Day 65 weekly review outputs, governance decisions, and KPI continuity signals.
- Every Day 66 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 66 closeout records GitLab pipeline stages, parallel matrix controls, cache strategy, and Day 67 integration priorities.

## Integration quality checklist

- [ ] Includes GitLab stages + rules path, matrix or parallel fan-out, and rollback trigger
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures pipeline pass-rate, median runtime, cache efficiency, confidence, and recovery owner
- [ ] Artifact pack includes integration brief, pipeline blueprint, matrix plan, KPI scorecard, and execution log

## Day 66 delivery board

- [ ] Day 66 integration brief committed
- [ ] Day 66 advanced GitLab pipeline blueprint published
- [ ] Day 66 matrix and cache strategy exported
- [ ] Day 66 KPI scorecard snapshot exported
- [ ] Day 67 integration expansion priorities drafted from Day 66 learnings

## Scoring model

Day 66 weighted score (0-100):

- Contract + command lane completeness: 25 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 65 continuity and strict baseline carryover: 30 points.
- GitLab reference quality + guardrails: 25 points.
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


def _load_day65(path: Path) -> tuple[int, bool, int]:
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


def build_day66_integration_expansion2_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    gitlab_text = _read(root / _GITLAB_PATH)

    day65_summary = root / _DAY65_SUMMARY_PATH
    day65_board = root / _DAY65_BOARD_PATH
    day65_score, day65_strict, day65_check_count = _load_day65(day65_summary)
    board_count, board_has_day65 = _count_board_items(day65_board, "Day 65")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_gitlab_lines = [x for x in _REQUIRED_GITLAB_LINES if x not in gitlab_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_day66_command",
            "weight": 7,
            "passed": ("day66-integration-expansion2-closeout" in readme_text),
            "evidence": "README day66 command lane",
        },
        {
            "check_id": "docs_index_day66_links",
            "weight": 8,
            "passed": (
                "day-66-big-upgrade-report.md" in docs_index_text
                and "integrations-day66-integration-expansion2-closeout.md" in docs_index_text
            ),
            "evidence": "day-66-big-upgrade-report.md + integrations-day66-integration-expansion2-closeout.md",
        },
        {
            "check_id": "top10_day66_alignment",
            "weight": 5,
            "passed": ("Day 66" in top10_text and "Day 67" in top10_text),
            "evidence": "Day 66 + Day 67 strategy chain",
        },
        {
            "check_id": "day65_summary_present",
            "weight": 10,
            "passed": day65_summary.exists(),
            "evidence": str(day65_summary),
        },
        {
            "check_id": "day65_delivery_board_present",
            "weight": 7,
            "passed": day65_board.exists(),
            "evidence": str(day65_board),
        },
        {
            "check_id": "day65_quality_floor",
            "weight": 13,
            "passed": day65_strict and day65_score >= 95,
            "evidence": {
                "day65_score": day65_score,
                "strict_pass": day65_strict,
                "day65_checks": day65_check_count,
            },
        },
        {
            "check_id": "day65_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_day65,
            "evidence": {"board_items": board_count, "contains_day65": board_has_day65},
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
            "check_id": "gitlab_reference_present",
            "weight": 10,
            "passed": not missing_gitlab_lines,
            "evidence": missing_gitlab_lines or _GITLAB_PATH,
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not day65_summary.exists() or not day65_board.exists():
        critical_failures.append("day65_handoff_inputs")
    if not day65_strict:
        critical_failures.append("day65_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day65_strict:
        wins.append(f"Day 65 continuity is strict-pass with activation score={day65_score}.")
    else:
        misses.append("Day 65 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 65 closeout command and restore strict baseline before Day 66 lock."
        )

    if board_count >= 5 and board_has_day65:
        wins.append(f"Day 65 delivery board integrity validated with {board_count} checklist items.")
    else:
        misses.append("Day 65 delivery board integrity is incomplete (needs >=5 items and Day 65 anchors).")
        handoff_actions.append("Repair Day 65 delivery board entries to include Day 65 anchors.")

    if not missing_gitlab_lines:
        wins.append("Day 66 GitLab reference pipeline is available for integration expansion execution.")
    else:
        misses.append("Day 66 GitLab reference pipeline is missing required controls.")
        handoff_actions.append("Update .gitlab-ci.day66-advanced-reference.yml to restore required controls.")

    if not failed and not critical_failures:
        wins.append(
            "Day 66 integration expansion #2 closeout lane is fully complete and ready for Day 67 integration expansion #3."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "day66-integration-expansion2-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "day65_summary": str(day65_summary.relative_to(root)) if day65_summary.exists() else str(day65_summary),
            "day65_delivery_board": str(day65_board.relative_to(root)) if day65_board.exists() else str(day65_board),
            "gitlab_reference": _GITLAB_PATH,
        },
        "checks": checks,
        "rollup": {
            "day65_activation_score": day65_score,
            "day65_checks": day65_check_count,
            "day65_delivery_board_items": board_count,
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
        "Day 66 integration expansion #2 closeout summary",
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
        target / "day66-integration-expansion2-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "day66-integration-expansion2-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "day66-integration-brief.md", "# Day 66 integration brief\n")
    _write(target / "day66-pipeline-blueprint.md", "# Day 66 pipeline blueprint\n")
    _write(target / "day66-matrix-plan.json", json.dumps({"matrix": []}, indent=2) + "\n")
    _write(target / "day66-kpi-scorecard.json", json.dumps({"kpis": []}, indent=2) + "\n")
    _write(target / "day66-execution-log.md", "# Day 66 execution log\n")
    _write(
        target / "day66-delivery-board.md",
        "\n".join(["# Day 66 delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "day66-validation-commands.md",
        "# Day 66 validation commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
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
        out_dir / "day66-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 66 integration expansion #2 closeout checks")
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
        _write(root / _PAGE_PATH, _DAY66_DEFAULT_PAGE)

    payload = build_day66_integration_expansion2_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day66-integration-expansion2-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
