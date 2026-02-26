from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-day48-objection-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_DAY47_SUMMARY_PATH = (
    "docs/artifacts/day47-reliability-closeout-pack/day47-reliability-closeout-summary.json"
)
_DAY47_BOARD_PATH = "docs/artifacts/day47-reliability-closeout-pack/day47-delivery-board.md"
_SECTION_HEADER = "# Day 48 — Objection closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Day 48 matters",
    "## Required inputs (Day 47)",
    "## Day 48 command lane",
    "## Objection closeout contract",
    "## Objection quality checklist",
    "## Day 48 delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit day48-objection-closeout --format json --strict",
    "python -m sdetkit day48-objection-closeout --emit-pack-dir docs/artifacts/day48-objection-closeout-pack --format json --strict",
    "python -m sdetkit day48-objection-closeout --execute --evidence-dir docs/artifacts/day48-objection-closeout-pack/evidence --format json --strict",
    "python scripts/check_day48_objection_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit day48-objection-closeout --format json --strict",
    "python -m sdetkit day48-objection-closeout --emit-pack-dir docs/artifacts/day48-objection-closeout-pack --format json --strict",
    "python scripts/check_day48_objection_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for Day 48 objection lane execution and KPI follow-up.",
    "The Day 48 objection lane references Day 47 reliability winners and misses with deterministic objection-handling loops.",
    "Every Day 48 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.",
    "Day 48 closeout records objection-handling learnings and Day 49 weekly-review priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes objection summary, FAQ update map, and rollback strategy",
    "- [ ] Every section has owner, publish window, KPI target, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI",
    "- [ ] Artifact pack includes objection plan, FAQ map, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ] Day 48 objection plan draft committed",
    "- [ ] Day 48 review notes captured with owner + backup",
    "- [ ] Day 48 FAQ objection map exported",
    "- [ ] Day 48 KPI scorecard snapshot exported",
    "- [ ] Day 49 weekly-review priorities drafted from Day 48 learnings",
]

_DAY48_DEFAULT_PAGE = """# Day 48 — Objection closeout lane

Day 48 closes with a major objection-handling upgrade that converts Day 47 reliability evidence into deterministic documentation hardening loops.

## Why Day 48 matters

- Converts Day 47 reliability proof into objection-first adoption motion.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from objection outcomes into Day 49 weekly-review priorities.

## Required inputs (Day 47)

- `docs/artifacts/day47-reliability-closeout-pack/day47-reliability-closeout-summary.json`
- `docs/artifacts/day47-reliability-closeout-pack/day47-delivery-board.md`

## Day 48 command lane

```bash
python -m sdetkit day48-objection-closeout --format json --strict
python -m sdetkit day48-objection-closeout --emit-pack-dir docs/artifacts/day48-objection-closeout-pack --format json --strict
python -m sdetkit day48-objection-closeout --execute --evidence-dir docs/artifacts/day48-objection-closeout-pack/evidence --format json --strict
python scripts/check_day48_objection_closeout_contract.py
```

## Objection closeout contract

- Single owner + backup reviewer are assigned for Day 48 objection lane execution and KPI follow-up.
- The Day 48 objection lane references Day 47 reliability winners and misses with deterministic objection-handling loops.
- Every Day 48 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Day 48 closeout records objection-handling learnings and Day 49 weekly-review priorities.

## Objection quality checklist

- [ ] Includes objection summary, FAQ update map, and rollback strategy
- [ ] Every section has owner, publish window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes objection plan, FAQ map, KPI scorecard, and execution log

## Day 48 delivery board

- [ ] Day 48 objection plan draft committed
- [ ] Day 48 review notes captured with owner + backup
- [ ] Day 48 FAQ objection map exported
- [ ] Day 48 KPI scorecard snapshot exported
- [ ] Day 49 weekly-review priorities drafted from Day 48 learnings

## Scoring model

Day 48 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 47 continuity and strict baseline carryover: 35 points.
- Objection contract lock + delivery board readiness: 15 points.
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


def _load_day47(path: Path) -> tuple[float, bool, int]:
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
    return len(items), "Day 47" in text, "Day 48" in text


def _contains_all_lines(text: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line not in text]


def build_day48_objection_closeout_summary(root: Path) -> dict[str, Any]:
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

    day47_summary = root / _DAY47_SUMMARY_PATH
    day47_board = root / _DAY47_BOARD_PATH
    day47_score, day47_strict, day47_check_count = _load_day47(day47_summary)
    board_count, board_has_day47, board_has_day48 = _board_stats(day47_board)

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
            "check_id": "readme_day48_link",
            "weight": 8,
            "passed": "docs/integrations-day48-objection-closeout.md" in readme_text,
            "evidence": "docs/integrations-day48-objection-closeout.md",
        },
        {
            "check_id": "readme_day48_command",
            "weight": 4,
            "passed": "day48-objection-closeout" in readme_text,
            "evidence": "day48-objection-closeout",
        },
        {
            "check_id": "docs_index_day48_links",
            "weight": 8,
            "passed": (
                "day-48-big-upgrade-report.md" in docs_index_text
                and "integrations-day48-objection-closeout.md" in docs_index_text
            ),
            "evidence": "day-48-big-upgrade-report.md + integrations-day48-objection-closeout.md",
        },
        {
            "check_id": "top10_day48_alignment",
            "weight": 5,
            "passed": ("Day 48" in top10_text and "Day 49" in top10_text),
            "evidence": "Day 48 + Day 49 strategy chain",
        },
        {
            "check_id": "day47_summary_present",
            "weight": 10,
            "passed": day47_summary.exists(),
            "evidence": str(day47_summary),
        },
        {
            "check_id": "day47_delivery_board_present",
            "weight": 8,
            "passed": day47_board.exists(),
            "evidence": str(day47_board),
        },
        {
            "check_id": "day47_quality_floor",
            "weight": 10,
            "passed": day47_strict and day47_score >= 95,
            "evidence": {
                "day47_score": day47_score,
                "strict_pass": day47_strict,
                "day47_checks": day47_check_count,
            },
        },
        {
            "check_id": "day47_board_integrity",
            "weight": 7,
            "passed": board_count >= 5 and board_has_day47 and board_has_day48,
            "evidence": {
                "board_items": board_count,
                "contains_day47": board_has_day47,
                "contains_day48": board_has_day48,
            },
        },
        {
            "check_id": "objection_contract_locked",
            "weight": 5,
            "passed": not missing_contract_lines,
            "evidence": {"missing_contract_lines": missing_contract_lines},
        },
        {
            "check_id": "objection_quality_checklist_locked",
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
    if not day47_summary.exists() or not day47_board.exists():
        critical_failures.append("day47_handoff_inputs")
    if not day47_strict:
        critical_failures.append("day47_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if day47_strict:
        wins.append(f"Day 47 continuity is strict-pass with activation score={day47_score}.")
    else:
        misses.append("Day 47 strict continuity signal is missing.")
        handoff_actions.append(
            "Re-run Day 47 reliability closeout command and restore strict pass baseline before Day 48 lock."
        )

    if board_count >= 5 and board_has_day47 and board_has_day48:
        wins.append(
            f"Day 47 delivery board integrity validated with {board_count} checklist items."
        )
    else:
        misses.append(
            "Day 47 delivery board integrity is incomplete (needs >=5 items and Day 47/48 anchors)."
        )
        handoff_actions.append(
            "Repair Day 47 delivery board entries to include Day 47 and Day 48 anchors."
        )

    if not missing_contract_lines and not missing_quality_lines and not missing_board_items:
        wins.append(
            "Objection execution contract + quality checklist is fully locked for execution."
        )
    else:
        misses.append(
            "Objection contract, quality checklist, or delivery board entries are missing."
        )
        handoff_actions.append(
            "Complete all Day 48 objection contract lines, quality checklist entries, and delivery board tasks in docs."
        )

    if not failed and not critical_failures:
        wins.append(
            "Day 48 objection closeout lane is fully complete and ready for Day 49 weekly-review lane."
        )

    return {
        "name": "day48-objection-closeout",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
            "day47_summary": str(day47_summary.relative_to(root))
            if day47_summary.exists()
            else str(day47_summary),
            "day47_delivery_board": str(day47_board.relative_to(root))
            if day47_board.exists()
            else str(day47_board),
        },
        "checks": checks,
        "rollup": {
            "day47_activation_score": day47_score,
            "day47_checks": day47_check_count,
            "day47_delivery_board_items": board_count,
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
        "Day 48 objection closeout summary",
        f"- Activation score: {payload['summary']['activation_score']}",
        f"- Passed checks: {payload['summary']['passed_checks']}",
        f"- Failed checks: {payload['summary']['failed_checks']}",
        f"- Critical failures: {payload['summary']['critical_failures']}",
        f"- Day 47 activation score: `{payload['rollup']['day47_activation_score']}`",
        f"- Day 47 checks evaluated: `{payload['rollup']['day47_checks']}`",
        f"- Day 47 delivery board checklist items: `{payload['rollup']['day47_delivery_board_items']}`",
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
    _write(target / "day48-objection-closeout-summary.json", json.dumps(payload, indent=2) + "\n")
    _write(target / "day48-objection-closeout-summary.md", _render_text(payload) + "\n")
    _write(
        target / "day48-objection-plan.md",
        "# Day 48 Objection Plan\n\n- Objective: close Day 48 with measurable objection-resolution and adoption gains.\n",
    )
    _write(
        target / "day48-faq-objection-map.csv",
        "stream,owner,backup,publish_window,docs_cta,command_cta,kpi_target,risk_flag\n"
        "objection-floor,qa-lead,docs-owner,2026-03-16T10:00:00Z,docs/integrations-day48-objection-closeout.md,python -m sdetkit day48-objection-closeout --format json --strict,failed-checks:0,faq-drift\n",
    )
    _write(
        target / "day48-objection-kpi-scorecard.json",
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
        target / "day48-execution-log.md",
        "# Day 48 Execution Log\n\n- [ ] 2026-03-16: Record misses, wins, and Day 49 weekly-review priorities.\n",
    )
    _write(
        target / "day48-delivery-board.md",
        "# Day 48 Delivery Board\n\n" + "\n".join(_REQUIRED_DELIVERY_BOARD_LINES) + "\n",
    )
    _write(
        target / "day48-validation-commands.md",
        "# Day 48 Validation Commands\n\n```bash\n" + "\n".join(_EXECUTION_COMMANDS) + "\n```\n",
    )


def _execute_commands(root: Path, evidence_dir: Path) -> None:
    evidence_path = root / evidence_dir
    evidence_path.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = []
    for index, command in enumerate(_EXECUTION_COMMANDS, start=1):
        proc = subprocess.run(
            shlex.split(command), cwd=root, text=True, capture_output=True, check=False
        )
        event = {
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        events.append(event)
        _write(evidence_path / f"command-{index:02d}.log", json.dumps(event, indent=2) + "\n")
    _write(
        evidence_path / "day48-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 48 objection closeout checks")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--emit-pack-dir")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--ensure-doc", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    if ns.ensure_doc:
        page = root / _PAGE_PATH
        if not page.exists():
            _write(page, _DAY48_DEFAULT_PAGE)

    payload = build_day48_objection_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, payload, Path(ns.emit_pack_dir))
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/day48-objection-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    if ns.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
