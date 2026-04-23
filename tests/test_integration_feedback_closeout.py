from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import integration_feedback_closeout_82 as d82


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-integration-feedback-closeout.md\nintegration-feedback-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-82-big-upgrade-report.md\nintegrations-integration-feedback-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Growth campaign closeout:** convert partner outcomes into deterministic campaign controls.\n"
        "- ** — Integration feedback loop:** fold field feedback into docs/templates.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-integration-feedback-closeout.md").write_text(
        d82._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-82-big-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = (
        root / "docs/artifacts/growth-campaign-closeout-pack/growth-campaign-closeout-summary.json"
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
    board = root / "docs/artifacts/growth-campaign-closeout-pack/growth-campaign-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  integration brief committed",
                "- [ ]  growth campaign plan committed",
                "- [ ]  campaign execution ledger exported",
                "- [ ]  campaign KPI scorecard snapshot exported",
                "- [ ]  execution priorities drafted from  learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/integration-feedback-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "integration-feedback-001",
                "contributors": ["maintainers", "docs-ops"],
                "feedback_channels": ["office-hours", "issues"],
                "baseline": {"feedback_items": 24, "docs_resolution_rate": 0.58},
                "target": {"feedback_items": 40, "docs_resolution_rate": 0.75},
                "owner": "docs-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_lane82_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d82.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "integration-feedback-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane82_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d82.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/integration-feedback-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/integration-feedback-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/integration-feedback-pack/integration-feedback-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/integration-feedback-pack/integration-feedback-closeout-summary.md"
    ).exists()
    assert (
        tmp_path / "artifacts/integration-feedback-pack/integration-feedback-integration-brief.md"
    ).exists()
    assert (tmp_path / "artifacts/integration-feedback-pack/integration-feedback-plan.md").exists()
    assert (
        tmp_path
        / "artifacts/integration-feedback-pack/integration-feedback-template-upgrade-ledger.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/integration-feedback-pack/integration-feedback-office-hours-outcomes-ledger.json"
    ).exists()
    assert (
        tmp_path / "artifacts/integration-feedback-pack/integration-feedback-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path / "artifacts/integration-feedback-pack/integration-feedback-execution-log.md"
    ).exists()
    assert (
        tmp_path / "artifacts/integration-feedback-pack/integration-feedback-delivery-board.md"
    ).exists()
    assert (
        tmp_path / "artifacts/integration-feedback-pack/integration-feedback-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/integration-feedback-pack/evidence/integration-feedback-execution-summary.json"
    ).exists()


def test_lane82_strict_fails_without_prereq_baseline(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/growth-campaign-closeout-pack/growth-campaign-closeout-summary.json"
    ).unlink()
    assert d82.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane82_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["integration-feedback-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert " integration feedback closeout summary" in capsys.readouterr().out
