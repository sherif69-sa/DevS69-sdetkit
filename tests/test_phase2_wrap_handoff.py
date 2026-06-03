from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import release_readiness_wrap_handoff as d60
from tests.workflow_fixture_seed import seed_contract_anchors


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-phase2-wrap-handoff-completion.md\nrelease-readiness-wrap-handoff-completion-report\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-60-big-upgrade-report.md\nintegrations-phase2-wrap-handoff-workflow.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Phase-2 wrap + handoff:** publish full Phase-2 report and lock Phase-3 execution board.\n"
        "- ** — Phase-3 kickoff:** set Phase-3 baseline and define ecosystem/trust KPIs.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-phase2-wrap-handoff-completion.md").write_text(
        d60._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-60-big-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-completion-report-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 100, "strict_pass": True},
                "checks": [{"passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = (
        root
        / "docs/artifacts/platform-readiness-preplan-completion-report-pack/phase3-preplan-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  Phase-3 pre-plan brief committed",
                "- [ ]  pre-plan reviewed with owner + backup",
                "- [ ]  risk ledger exported",
                "- [ ]  KPI scorecard snapshot exported",
                "- [ ]  execution priorities drafted from  learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-phase2-wrap-handoff.md").write_text(
        """# Phase 2 Wrap Handoff Closeout - Phase-2 wrap + handoff closeout lane

## Why Phase 2 Wrap Handoff Closeout matters

The Phase-2 wrap + handoff workflow keeps Phase-2 outcomes connected to Phase-3 execution priorities.

## Required inputs (Phase-3 pre-plan closeout)

Use the Phase-3 pre-plan summary and delivery board before promoting the handoff.

## Phase 2 Wrap Handoff Closeout command lane

python -m sdetkit release-readiness-wrap-handoff-completion-report --format json --strict
python -m sdetkit release-readiness-wrap-handoff-completion-report --emit-pack-dir docs/artifacts/release-readiness-wrap-handoff-completion-report-pack --format json --strict
python -m sdetkit release-readiness-wrap-handoff-completion-report --execute --evidence-dir docs/artifacts/release-readiness-wrap-handoff-completion-report-pack/evidence --format json --strict
python scripts/check_phase2_wrap_handoff_contract.py

## Phase-2 wrap + handoff contract

Single owner + backup reviewer are assigned for Phase-2 wrap + handoff execution and signal triage.
The closeout lane references Phase-3 pre-plan outcomes and unresolved risks.
Every section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
This closeout records Phase-2 wrap outcomes and Phase-3 execution priorities.

## Phase-2 wrap + handoff quality checklist

- [ ] Includes priority digest, lane-level plan actions, and rollback strategy
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI
- [ ] Artifact pack includes wrap brief, risk ledger, KPI scorecard, and execution log

## Phase 2 Wrap Handoff Closeout delivery board

- [ ] Phase-2 wrap + handoff brief committed
- [ ] Wrap reviewed with owner + backup
- [ ] Risk ledger exported
- [ ] KPI scorecard snapshot exported
- [ ] Phase-3 execution priorities drafted from Phase-2 learnings

## Scoring model

Activation score must stay above the strict promotion floor.
""",
        encoding="utf-8",
    )


def test_phase2_wrap_handoff_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d60.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "release-readiness-wrap-handoff-completion-report"
    assert out["summary"]["activation_score"] >= 95
    assert "## Required inputs ()" not in d60._DEFAULT_PAGE_TEMPLATE
    assert "The  lane references" not in d60._DEFAULT_PAGE_TEMPLATE
    assert "## Why  matters" not in d60._DEFAULT_PAGE_TEMPLATE


def test_phase2_wrap_handoff_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d60.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/release-readiness-wrap-handoff-completion-report-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/release-readiness-wrap-handoff-completion-report-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/release-readiness-wrap-handoff-completion-report-pack/release-readiness-wrap-handoff-completion-report-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-wrap-handoff-completion-report-pack/release-readiness-wrap-handoff-completion-report-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-wrap-handoff-completion-report-pack/phase2-wrap-handoff-brief.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-wrap-handoff-completion-report-pack/phase2-wrap-handoff-risk-ledger.csv"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-wrap-handoff-completion-report-pack/phase2-wrap-handoff-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-wrap-handoff-completion-report-pack/phase2-wrap-handoff-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-wrap-handoff-completion-report-pack/phase2-wrap-handoff-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-wrap-handoff-completion-report-pack/phase2-wrap-handoff-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-wrap-handoff-completion-report-pack/evidence/phase2-wrap-handoff-execution-summary.json"
    ).exists()


def test_phase2_wrap_handoff_strict_fails_without_phase3_preplan(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    (
        tmp_path
        / "docs/artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-completion-report-summary.json"
    ).unlink()
    assert d60.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_phase2_wrap_handoff_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = cli.main(
        [
            "release-readiness-wrap-handoff-completion-report",
            "--root",
            str(tmp_path),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    assert "Phase 2 Wrap Handoff Closeout summary" in capsys.readouterr().out


def test_phase2_wrap_handoff_docs_page_has_no_lane_lane_typo() -> None:
    docs_page = (
        Path(__file__).resolve().parents[1] / "docs/integrations-phase2-wrap-handoff-completion.md"
    )
    page_text = docs_page.read_text(encoding="utf-8")
    assert "Lane lane" not in page_text
