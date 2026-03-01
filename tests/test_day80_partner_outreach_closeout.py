from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day80_partner_outreach_closeout as d80


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day80-partner-outreach-closeout.md\nday80-partner-outreach-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-80-big-upgrade-report.md\nintegrations-day80-partner-outreach-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 79 — Scale upgrade closeout:** lock enterprise onboarding improvements.\n"
        "- **Day 80 — Partner outreach closeout:** publish partner onboarding execution checklist.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day80-partner-outreach-closeout.md").write_text(
        d80._DAY80_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-80-big-upgrade-report.md").write_text("# Day 80 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day79-scale-upgrade-closeout-pack/day79-scale-upgrade-closeout-summary.json"
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
    board = root / "docs/artifacts/day79-scale-upgrade-closeout-pack/day79-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 79 delivery board",
                "- [ ] Day 79 integration brief committed",
                "- [ ] Day 79 scale upgrade plan committed",
                "- [ ] Day 79 enterprise execution ledger exported",
                "- [ ] Day 79 enterprise KPI scorecard snapshot exported",
                "- [ ] Day 80 partner outreach priorities drafted from Day 79 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/day80-partner-outreach-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day80-partner-outreach-001",
                "contributors": ["maintainers", "partner-success"],
                "partner_tracks": ["partner-onboarding", "joint-go-to-market"],
                "baseline": {"activated_partners": 4, "sla_days": 9},
                "target": {"activated_partners": 8, "sla_days": 5},
                "owner": "partner-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day80_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d80.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day80-partner-outreach-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day80_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d80.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day80-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day80-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day80-pack/day80-partner-outreach-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day80-pack/day80-partner-outreach-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day80-pack/day80-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day80-pack/day80-partner-outreach-plan.md").exists()
    assert (tmp_path / "artifacts/day80-pack/day80-partner-execution-ledger.json").exists()
    assert (tmp_path / "artifacts/day80-pack/day80-partner-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day80-pack/day80-execution-log.md").exists()
    assert (tmp_path / "artifacts/day80-pack/day80-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day80-pack/day80-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day80-pack/evidence/day80-execution-summary.json").exists()


def test_day80_strict_fails_without_day79(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day79-scale-upgrade-closeout-pack/day79-scale-upgrade-closeout-summary.json"
    ).unlink()
    assert d80.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day80_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day80-partner-outreach-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 80 partner outreach closeout summary" in capsys.readouterr().out
