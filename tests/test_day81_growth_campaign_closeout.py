from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day81_growth_campaign_closeout as d81


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day81-growth-campaign-closeout.md\nday81-growth-campaign-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-81-big-upgrade-report.md\nintegrations-day81-growth-campaign-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 80 — Partner outreach closeout:** publish partner onboarding execution checklist.\n"
        "- **Day 81 — Growth campaign closeout:** convert partner outcomes into deterministic campaign controls.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day81-growth-campaign-closeout.md").write_text(
        d81._DAY81_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-81-big-upgrade-report.md").write_text("# Day 81 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day80-partner-outreach-closeout-pack/day80-partner-outreach-closeout-summary.json"
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
    board = root / "docs/artifacts/day80-partner-outreach-closeout-pack/day80-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 80 delivery board",
                "- [ ] Day 80 integration brief committed",
                "- [ ] Day 80 partner outreach plan committed",
                "- [ ] Day 80 partner execution ledger exported",
                "- [ ] Day 80 partner KPI scorecard snapshot exported",
                "- [ ] Day 81 growth campaign priorities drafted from Day 80 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / ".day81-growth-campaign-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day81-growth-campaign-001",
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


def test_day81_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d81.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day81-growth-campaign-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day81_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d81.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day81-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day81-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day81-pack/day81-growth-campaign-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day81-pack/day81-growth-campaign-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day81-pack/day81-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day81-pack/day81-growth-campaign-plan.md").exists()
    assert (tmp_path / "artifacts/day81-pack/day81-campaign-execution-ledger.json").exists()
    assert (tmp_path / "artifacts/day81-pack/day81-campaign-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day81-pack/day81-execution-log.md").exists()
    assert (tmp_path / "artifacts/day81-pack/day81-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day81-pack/day81-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day81-pack/evidence/day81-execution-summary.json").exists()


def test_day81_strict_fails_without_day80(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day80-partner-outreach-closeout-pack/day80-partner-outreach-closeout-summary.json"
    ).unlink()
    assert d81.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day81_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day81-growth-campaign-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 81 growth campaign closeout summary" in capsys.readouterr().out
