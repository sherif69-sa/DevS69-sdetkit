from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import release_prioritization as d85
from tests.workflow_fixture_seed import seed_contract_anchors


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-release-prioritization-completion.md\nrelease-prioritization-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-85-big-upgrade-report.md\nintegrations-release-prioritization-workflow.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Evidence narrative closeout lane:** convert field objections into deterministic trust upgrades.\n"
        "- ** — Release prioritization closeout lane:** convert trust outcomes into release-ready narrative proof packs.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-release-prioritization-completion.md").write_text(
        d85._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-85-big-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/evidence-narrative-closeout-pack/evidence-narrative-closeout-summary.json"
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
        / "docs/artifacts/evidence-narrative-closeout-pack/evidence-narrative-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  evidence brief committed",
                "- [ ]  evidence narrative plan committed",
                "- [ ]  narrative template upgrade ledger exported",
                "- [ ]  storyline outcomes ledger exported",
                "- [ ]  release priorities drafted from  outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/release-prioritization-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "release-prioritization-001",
                "contributors": ["maintainers", "docs-ops"],
                "narrative_channels": ["release-report", "runbook", "faq"],
                "baseline": {"evidence_coverage": 0.64, "narrative_reuse": 0.42},
                "target": {"evidence_coverage": 0.86, "narrative_reuse": 0.67},
                "owner": "docs-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "docs/integrations-release-prioritization.md").write_text(
        """# Release Prioritization Closeout — Release prioritization closeout lane

## Why Release Prioritization Closeout matters

The release prioritization workflow keeps evidence narrative outcomes connected to launch priority decisions.

## Required inputs (Release prioritization closeout lane)

Use evidence narrative outcomes, controls, trust continuity signals, and the release prioritization plan.

## Command lane

python -m sdetkit release-prioritization-closeout --format json --strict
python -m sdetkit release-prioritization-closeout --emit-pack-dir docs/artifacts/release-prioritization-closeout-pack --format json --strict
python -m sdetkit release-prioritization-closeout --execute --evidence-dir docs/artifacts/release-prioritization-closeout-pack/evidence --format json --strict
python scripts/check_release_prioritization_contract.py

## Release prioritization contract

Single owner + backup reviewer are assigned for this release prioritization execution and signoff.
This lane references evidence narrative outcomes, controls, and trust continuity signals.
Every section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.
This closeout records release prioritization pack upgrades, storyline outcomes, and launch priorities.

## Release prioritization quality checklist

- [ ] Includes baseline evidence coverage, objection segmentation assumptions, and response SLA targets
- [ ] Every narrative lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to narrative docs/templates + runnable command evidence
- [ ] Scorecard captures release prioritization adoption delta, objection deflection delta, confidence, and rollback owner
- [ ] Artifact pack includes narrative brief, evidence plan, template diffs, outcome ledger, KPI scorecard, and execution log

## Delivery board

- [ ] Release prioritization evidence brief committed
- [ ] Release prioritization plan committed
- [ ] Narrative template upgrade ledger exported
- [ ] Storyline outcomes ledger exported
- [ ] Launch priorities drafted from evidence narrative outcomes

## Scoring model

Activation score must stay above the strict promotion floor.
""",
        encoding="utf-8",
    )


def test_release_prioritization_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d85.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "release-prioritization-closeout"
    assert out["summary"]["activation_score"] >= 95
    assert "Lane lane" not in d85._DEFAULT_PAGE_TEMPLATE
    assert "## Required inputs ()" not in d85._DEFAULT_PAGE_TEMPLATE


def test_release_prioritization_board_keyword_required(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    board = (
        tmp_path
        / "docs/artifacts/evidence-narrative-closeout-pack/evidence-narrative-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# release delivery board",
                "- [ ] Release prioritization evidence brief committed",
                "- [ ] Release prioritization plan committed",
                "- [ ] Narrative template upgrade ledger exported",
                "- [ ] Storyline outcomes ledger exported",
                "- [ ] Launch priorities drafted from outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rc = d85.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    evidence_check = next(
        c for c in out["checks"] if c["check_id"] == "evidence_narrative_board_integrity"
    )
    assert evidence_check["passed"] is False
    assert out["summary"]["strict_pass"] is False


def test_release_prioritization_docs_page_matches_default_template() -> None:
    docs_page = (
        Path(__file__).resolve().parents[1]
        / "docs/integrations-release-prioritization-completion.md"
    )
    page_text = docs_page.read_text(encoding="utf-8")
    assert "Lane lane" not in page_text
    assert "## Required inputs ()" not in page_text
    assert d85._SECTION_HEADER in page_text
    for line in d85._REQUIRED_CONTRACT_LINES:
        assert line in page_text


def test_release_prioritization_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d85.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/release-prioritization-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/release-prioritization-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-closeout-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-closeout-summary.md"
    ).exists()
    assert (
        tmp_path / "artifacts/release-prioritization-pack/release-prioritization-evidence-brief.md"
    ).exists()
    assert (
        tmp_path / "artifacts/release-prioritization-pack/release-prioritization-plan.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-narrative-template-upgrade-ledger.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-storyline-outcomes-ledger.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-narrative-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path / "artifacts/release-prioritization-pack/release-prioritization-execution-log.md"
    ).exists()
    assert (
        tmp_path / "artifacts/release-prioritization-pack/release-prioritization-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/evidence/release-prioritization-execution-summary.json"
    ).exists()


def test_release_prioritization_strict_fails_without_prereq_baseline(
    tmp_path: Path,
) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    (
        tmp_path
        / "docs/artifacts/evidence-narrative-closeout-pack/evidence-narrative-closeout-summary.json"
    ).unlink()
    assert d85.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_release_prioritization_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = cli.main(["release-prioritization-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert " release prioritization closeout summary" in capsys.readouterr().out
