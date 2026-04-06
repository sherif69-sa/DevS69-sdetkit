from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import distribution_scaling_closeout_74 as d74


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-distribution-scaling-closeout.md\ndistribution-scaling-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-74-big-upgrade-report.md\nintegrations-distribution-scaling-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Distribution scaling:** convert  learnings into scaled channel operations.\n"
        "- ** — Trust assets refresh:** turn  outcomes into governance-grade trust proof.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-distribution-scaling-closeout.md").write_text(
        d74._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-74-big-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/case-study-launch-closeout-pack/case-study-launch-closeout-summary.json"
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
        root / "docs/artifacts/case-study-launch-closeout-pack/case-study-launch-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  integration brief committed",
                "- [ ]  published case-study narrative committed",
                "- [ ]  controls and assumptions log exported",
                "- [ ]  KPI scorecard snapshot exported",
                "- [ ]  distribution scaling priorities drafted from  learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scaling_plan = root / "docs/roadmap/plans/distribution-scaling-plan.json"
    scaling_plan.write_text(
        json.dumps(
            {
                "plan_id": "distribution-scaling-001",
                "channels": ["github", "linkedin", "newsletter"],
                "baseline": {"qualified_leads": 22, "ctr": 0.038},
                "target": {"qualified_leads": 35, "ctr": 0.051},
                "confidence": 0.9,
                "owner": "growth-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_lane74_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d74.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "distribution-scaling-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane74_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d74.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/distribution-scaling-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/distribution-scaling-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/distribution-scaling-closeout-pack/distribution-scaling-closeout-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/distribution-scaling-closeout-pack/distribution-scaling-closeout-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/distribution-scaling-closeout-pack/distribution-scaling-integration-brief.md"
    ).exists()
    assert (
        tmp_path / "artifacts/distribution-scaling-closeout-pack/distribution-scaling-plan.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/distribution-scaling-closeout-pack/distribution-scaling-channel-controls-log.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/distribution-scaling-closeout-pack/distribution-scaling-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/distribution-scaling-closeout-pack/distribution-scaling-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/distribution-scaling-closeout-pack/distribution-scaling-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/distribution-scaling-closeout-pack/distribution-scaling-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/distribution-scaling-closeout-pack/evidence/distribution-scaling-execution-summary.json"
    ).exists()


def test_lane74_strict_fails_without_prior_closeout(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/case-study-launch-closeout-pack/case-study-launch-closeout-summary.json"
    ).unlink()
    assert d74.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane74_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["distribution-scaling-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Distribution Scaling Closeout summary" in capsys.readouterr().out
