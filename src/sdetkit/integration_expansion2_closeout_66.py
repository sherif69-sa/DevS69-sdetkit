from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bools import coerce_bool

_PAGE_PATH = "docs/integrations-integration-expansion2-closeout.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_WEEKLY_REVIEW_SUMMARY_PATH = (
    "docs/artifacts/weekly-review-closeout-pack-2/weekly-review-closeout-summary-2.json"
)
_WEEKLY_REVIEW_BOARD_PATH = (
    "docs/artifacts/weekly-review-closeout-pack-2/weekly-review-closeout-delivery-board-2.md"
)
_GITLAB_PATH = "templates/ci/gitlab/gitlab-advanced-reference.yml"
_SECTION_HEADER = "#  — Integration expansion #2 closeout lane"
_REQUIRED_SECTIONS = [
    "## Why Integration Expansion 2 Closeout matters",
    "## Required inputs ()",
    "## Integration Expansion 2 Closeout command lane",
    "## Integration expansion contract",
    "## Integration quality checklist",
    "## Integration Expansion 2 Closeout delivery board",
    "## Scoring model",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit integration-expansion2-closeout --format json --strict",
    "python -m sdetkit integration-expansion2-closeout --emit-pack-dir docs/artifacts/integration-expansion2-closeout-pack --format json --strict",
    "python -m sdetkit integration-expansion2-closeout --execute --evidence-dir docs/artifacts/integration-expansion2-closeout-pack/evidence --format json --strict",
    "python scripts/check_integration_expansion2_closeout_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit integration-expansion2-closeout --format json --strict",
    "python -m sdetkit integration-expansion2-closeout --emit-pack-dir docs/artifacts/integration-expansion2-closeout-pack --format json --strict",
    "python scripts/check_integration_expansion2_closeout_contract.py --skip-evidence",
]
_REQUIRED_CONTRACT_LINES = [
    "Single owner + backup reviewer are assigned for  advanced GitLab CI rollout and signoff.",
    "The  lane references  weekly review outputs, governance decisions, and KPI continuity signals.",
    "Every  section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.",
    " closeout records GitLab pipeline stages, parallel matrix controls, cache strategy, and  integration priorities.",
]
_REQUIRED_QUALITY_LINES = [
    "- [ ] Includes GitLab stages + rules path, matrix or parallel fan-out, and rollback trigger",
    "- [ ] Every section has owner, review window, KPI threshold, and risk flag",
    "- [ ] CTA links point to docs + runnable command evidence",
    "- [ ] Scorecard captures pipeline pass-rate, median runtime, cache efficiency, confidence, and recovery owner",
    "- [ ] Artifact pack includes integration brief, pipeline blueprint, matrix plan, KPI scorecard, and execution log",
]
_REQUIRED_DELIVERY_BOARD_LINES = [
    "- [ ]  integration brief committed",
    "- [ ]  advanced GitLab pipeline blueprint published",
    "- [ ]  matrix and cache strategy exported",
    "- [ ]  KPI scorecard snapshot exported",
    "- [ ]  integration expansion priorities drafted from  learnings",
]
_REQUIRED_GITLAB_LINES = [
    "stages:",
    "workflow:",
    "rules:",
    "parallel:",
    "matrix:",
    "cache:",
]

_DEFAULT_PAGE_TEMPLATE = "#  — Integration expansion #2 closeout lane\n\n closes with a major integration upgrade that converts  weekly review outcomes into an advanced GitLab CI reference pipeline.\n\n## Why Integration Expansion 2 Closeout matters\n\n- Converts  governance outputs into reusable GitLab CI implementation patterns.\n- Protects integration outcomes with strict contract coverage, runnable commands, and rollback safety.\n- Creates a deterministic handoff from  integration expansion to  integration expansion #3.\n\n## Required inputs ()\n\n- `docs/artifacts/weekly-review-closeout-pack-2/weekly-review-closeout-summary-2.json`\n- `docs/artifacts/weekly-review-closeout-pack-2/weekly-review-closeout-delivery-board-2.md`\n- `templates/ci/gitlab/gitlab-advanced-reference.yml`\n\n## Integration Expansion 2 Closeout command lane\n\n```bash\npython -m sdetkit integration-expansion2-closeout --format json --strict\npython -m sdetkit integration-expansion2-closeout --emit-pack-dir docs/artifacts/integration-expansion2-closeout-pack --format json --strict\npython -m sdetkit integration-expansion2-closeout --execute --evidence-dir docs/artifacts/integration-expansion2-closeout-pack/evidence --format json --strict\npython scripts/check_integration_expansion2_closeout_contract.py\n```\n\n## Integration expansion contract\n\n- Single owner + backup reviewer are assigned for  advanced GitLab CI rollout and signoff.\n- The  lane references  weekly review outputs, governance decisions, and KPI continuity signals.\n- Every  section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.\n-  closeout records GitLab pipeline stages, parallel matrix controls, cache strategy, and  integration priorities.\n\n## Integration quality checklist\n\n- [ ] Includes GitLab stages + rules path, matrix or parallel fan-out, and rollback trigger\n- [ ] Every section has owner, review window, KPI threshold, and risk flag\n- [ ] CTA links point to docs + runnable command evidence\n- [ ] Scorecard captures pipeline pass-rate, median runtime, cache efficiency, confidence, and recovery owner\n- [ ] Artifact pack includes integration brief, pipeline blueprint, matrix plan, KPI scorecard, and execution log\n\n## Integration Expansion 2 Closeout delivery board\n\n- [ ]  integration brief committed\n- [ ]  advanced GitLab pipeline blueprint published\n- [ ]  matrix and cache strategy exported\n- [ ]  KPI scorecard snapshot exported\n- [ ]  integration expansion priorities drafted from  learnings\n\n## Scoring model\n\n weighted score (0-100):\n\n- Contract + command lane completeness: 25 points.\n- Discoverability alignment (README/docs index/top-10): 20 points.\n-  continuity and strict baseline carryover: 30 points.\n- GitLab reference quality + guardrails: 25 points.\n"


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


def _load_weekly_review(path: Path) -> tuple[int, bool, int]:
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


def build_integration_expansion2_closeout_summary(root: Path) -> dict[str, Any]:
    readme_text = _read(root / "README.md")
    docs_index_text = _read(root / "docs/index.md")
    page_text = _read(root / _PAGE_PATH)
    top10_text = _read(root / _TOP10_PATH)
    gitlab_path = root / _GITLAB_PATH
    gitlab_text = _read(gitlab_path)

    weekly_review_summary = root / _WEEKLY_REVIEW_SUMMARY_PATH
    weekly_review_board = root / _WEEKLY_REVIEW_BOARD_PATH
    weekly_review_score, weekly_review_strict, weekly_review_check_count = _load_weekly_review(
        weekly_review_summary
    )
    board_count, board_has_weekly_review = _count_board_items(weekly_review_board, "")

    missing_sections = [x for x in _REQUIRED_SECTIONS if x not in page_text]
    missing_commands = [x for x in _REQUIRED_COMMANDS if x not in page_text]
    missing_contract_lines = [x for x in _REQUIRED_CONTRACT_LINES if x not in page_text]
    missing_quality_lines = [x for x in _REQUIRED_QUALITY_LINES if x not in page_text]
    missing_board_items = [x for x in _REQUIRED_DELIVERY_BOARD_LINES if x not in page_text]
    missing_gitlab_lines = [x for x in _REQUIRED_GITLAB_LINES if x not in gitlab_text]

    checks: list[dict[str, Any]] = [
        {
            "check_id": "readme_command_lane",
            "weight": 7,
            "passed": ("integration-expansion2-closeout" in readme_text),
            "evidence": "README integration-expansion2-closeout command lane",
        },
        {
            "check_id": "docs_index_links",
            "weight": 8,
            "passed": (
                "impact-66-big-upgrade-report.md" in docs_index_text
                and "integrations-integration-expansion2-closeout.md" in docs_index_text
            ),
            "evidence": "impact-66-big-upgrade-report.md + integrations-integration-expansion2-closeout.md",
        },
        {
            "check_id": "top10_strategy_alignment",
            "weight": 5,
            "passed": ("" in top10_text and "" in top10_text),
            "evidence": " +  strategy chain",
        },
        {
            "check_id": "weekly_review_summary_present",
            "weight": 10,
            "passed": weekly_review_summary.exists(),
            "evidence": str(weekly_review_summary),
        },
        {
            "check_id": "weekly_review_delivery_board_present",
            "weight": 7,
            "passed": weekly_review_board.exists(),
            "evidence": str(weekly_review_board),
        },
        {
            "check_id": "weekly_review_quality_floor",
            "weight": 13,
            "passed": weekly_review_strict and weekly_review_score >= 95,
            "evidence": {
                "weekly_review_score": weekly_review_score,
                "strict_pass": weekly_review_strict,
                "weekly_review_checks": weekly_review_check_count,
            },
        },
        {
            "check_id": "weekly_review_board_integrity",
            "weight": 5,
            "passed": board_count >= 5 and board_has_weekly_review,
            "evidence": {
                "board_items": board_count,
                "contains_weekly_review": board_has_weekly_review,
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
            "check_id": "gitlab_reference_present",
            "weight": 10,
            "passed": not missing_gitlab_lines,
            "evidence": missing_gitlab_lines or str(gitlab_path.relative_to(root)),
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    critical_failures: list[str] = []
    if not weekly_review_summary.exists() or not weekly_review_board.exists():
        critical_failures.append("weekly_review_inputs")
    if not weekly_review_strict:
        critical_failures.append("weekly_review_strict_baseline")

    wins: list[str] = []
    misses: list[str] = []
    handoff_actions: list[str] = []

    if weekly_review_strict:
        wins.append(f"65 continuity is strict-pass with activation score={weekly_review_score}.")
    else:
        misses.append(" strict continuity signal is missing.")
        handoff_actions.append("Re-run  closeout command and restore strict baseline before  lock.")

    if board_count >= 5 and board_has_weekly_review:
        wins.append(f"65 delivery board integrity validated with {board_count} checklist items.")
    else:
        misses.append(" delivery board integrity is incomplete (needs >=5 items and  anchors).")
        handoff_actions.append("Repair  delivery board entries to include  anchors.")

    if not missing_gitlab_lines:
        wins.append(" GitLab reference pipeline is available for integration expansion execution.")
    else:
        misses.append(" GitLab reference pipeline is missing required controls.")
        handoff_actions.append(
            "Update templates/ci/gitlab/gitlab-advanced-reference.yml to restore required controls."
        )

    if not failed and not critical_failures:
        wins.append(
            " integration expansion #2 closeout lane is fully complete and ready for  integration expansion #3."
        )

    score = int(round(sum(c["weight"] for c in checks if c["passed"])))
    return {
        "name": "integration-expansion2-closeout",
        "inputs": {
            "readme": "README.md",
            "docs_index": "docs/index.md",
            "docs_page": _PAGE_PATH,
            "top10": _TOP10_PATH,
            "weekly_review_summary": str(weekly_review_summary.relative_to(root))
            if weekly_review_summary.exists()
            else str(weekly_review_summary),
            "weekly_review_delivery_board": str(weekly_review_board.relative_to(root))
            if weekly_review_board.exists()
            else str(weekly_review_board),
            "gitlab_reference": str(gitlab_path.relative_to(root))
            if gitlab_path.exists()
            else _GITLAB_PATH,
        },
        "checks": checks,
        "rollup": {
            "weekly_review_activation_score": weekly_review_score,
            "weekly_review_checks": weekly_review_check_count,
            "weekly_review_delivery_board_items": board_count,
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
        "Integration Expansion 2 Closeout summary",
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
        target / "integration-expansion2-closeout-summary.json",
        json.dumps(payload, indent=2) + "\n",
    )
    _write(target / "integration-expansion2-closeout-summary.md", _render_text(payload) + "\n")
    _write(target / "integration-expansion2-integration-brief.md", "#  integration brief\n")
    _write(target / "integration-expansion2-pipeline-blueprint.md", "#  pipeline blueprint\n")
    _write(
        target / "integration-expansion2-matrix-plan.json",
        json.dumps({"matrix": []}, indent=2) + "\n",
    )
    _write(
        target / "integration-expansion2-kpi-scorecard.json",
        json.dumps({"kpis": []}, indent=2) + "\n",
    )
    _write(target / "integration-expansion2-execution-log.md", "#  execution log\n")
    _write(
        target / "integration-expansion2-delivery-board.md",
        "\n".join(["#  delivery board", *_REQUIRED_DELIVERY_BOARD_LINES]) + "\n",
    )
    _write(
        target / "integration-expansion2-validation-commands.md",
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
        out_dir / "integration-expansion2-execution-summary.json",
        json.dumps({"total_commands": len(events), "commands": events}, indent=2) + "\n",
    )


def build_integration_expansion2_closeout_summary_impl(root: Path) -> dict[str, Any]:
    "Compatibility alias for legacy -based builder name."
    return build_integration_expansion2_closeout_summary(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=" integration expansion #2 closeout checks")
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

    payload = build_integration_expansion2_closeout_summary(root)

    if ns.emit_pack_dir:
        _emit_pack(root, Path(ns.emit_pack_dir), payload)
    if ns.execute:
        evidence_dir = (
            Path(ns.evidence_dir)
            if ns.evidence_dir
            else Path("docs/artifacts/integration-expansion2-closeout-pack/evidence")
        )
        _execute_commands(root, evidence_dir)

    print(json.dumps(payload, indent=2) if ns.format == "json" else _render_text(payload))
    return 1 if ns.strict and not payload["summary"]["strict_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
