from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import growth_campaign_closeout_81 as d81


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-growth-campaign-closeout.md\ngrowth-campaign-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-81-big-upgrade-report.md\nintegrations-growth-campaign-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        '- ** — Partner outreach closeout:** publish partner onboarding execution checklist.\n'
        '- ** — Growth campaign closeout:** convert partner outcomes into deterministic campaign controls.\n',
        encoding="utf-8",
    )
    (root / "docs/integrations-growth-campaign-closeout.md").write_text(
        d81._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-81-big-upgrade-report.md").write_text(
        '#  report\n', encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/partner-outreach-closeout-pack/partner-outreach-closeout-summary.json"
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
        root / "docs/artifacts/partner-outreach-closeout-pack/partner-outreach-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                '#  delivery board',
                '- [ ]  integration brief committed',
                '- [ ]  partner outreach plan committed',
                '- [ ]  partner execution ledger exported',
                '- [ ]  partner KPI scorecard snapshot exported',
                '- [ ]  growth campaign priorities drafted from  learnings',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/growth-campaign-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "growth-campaign-001",
                "contributors": ["maintainers", "growth-ops"],
                "campaign_tracks": ["activation", "retention"],
                "baseline": {"leads": 90, "activation_rate": 0.22},
                "target": {"leads": 160, "activation_rate": 0.31},
                "owner": "growth-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_lane81_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d81.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "growth-campaign-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane81_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d81.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/growth-campaign-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/growth-campaign-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/growth-campaign-pack/growth-campaign-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/growth-campaign-pack/growth-campaign-closeout-summary.md"
    ).exists()
    assert (
        tmp_path / "artifacts/growth-campaign-pack/growth-campaign-integration-brief.md"
    ).exists()
    assert (tmp_path / "artifacts/growth-campaign-pack/growth-campaign-plan.md").exists()
    assert (
        tmp_path / "artifacts/growth-campaign-pack/growth-campaign-campaign-execution-ledger.json"
    ).exists()
    assert (
        tmp_path / "artifacts/growth-campaign-pack/growth-campaign-campaign-kpi-scorecard.json"
    ).exists()
    assert (tmp_path / "artifacts/growth-campaign-pack/growth-campaign-execution-log.md").exists()
    assert (tmp_path / "artifacts/growth-campaign-pack/growth-campaign-delivery-board.md").exists()
    assert (
        tmp_path / "artifacts/growth-campaign-pack/growth-campaign-validation-commands.md"
    ).exists()
    assert (
        tmp_path / "artifacts/growth-campaign-pack/evidence/growth-campaign-execution-summary.json"
    ).exists()


def test_lane81_strict_fails_without_prereq_baseline(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/partner-outreach-closeout-pack/partner-outreach-closeout-summary.json"
    ).unlink()
    assert d81.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane81_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["growth-campaign-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert ' growth campaign closeout summary' in capsys.readouterr().out
