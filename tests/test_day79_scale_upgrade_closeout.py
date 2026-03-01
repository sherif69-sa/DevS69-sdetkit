from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day79_scale_upgrade_closeout as d79


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day79-scale-upgrade-closeout.md\nday79-scale-upgrade-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-79-big-upgrade-report.md\nintegrations-day79-scale-upgrade-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 78 — Ecosystem priorities closeout:** lock partner workflow baselines.\n"
        "- **Day 79 — Enterprise onboarding path:** publish role-based onboarding checklist.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day79-scale-upgrade-closeout.md").write_text(
        d79._DAY79_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-79-big-upgrade-report.md").write_text("# Day 79 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day78-ecosystem-priorities-closeout-pack/day78-ecosystem-priorities-closeout-summary.json"
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
    board = root / "docs/artifacts/day78-ecosystem-priorities-closeout-pack/day78-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 78 delivery board",
                "- [ ] Day 78 integration brief committed",
                "- [ ] Day 78 ecosystem priorities plan committed",
                "- [ ] Day 78 ecosystem workstream ledger exported",
                "- [ ] Day 78 ecosystem KPI scorecard snapshot exported",
                "- [ ] Day 79 scale priorities drafted from Day 78 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scale_plan = root / "docs/roadmap/plans/day79-scale-upgrade-plan.json"
    scale_plan.write_text(
        json.dumps(
            {
                "plan_id": "day79-scale-upgrade-001",
                "contributors": ["maintainers", "enterprise-success"],
                "scale_tracks": ["role-based-onboarding", "control-plane-rollout"],
                "baseline": {"activated_orgs": 3, "setup_time_days": 12},
                "target": {"activated_orgs": 6, "setup_time_days": 7},
                "owner": "enterprise-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day79_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d79.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day79-scale-upgrade-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day79_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d79.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day79-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day79-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day79-pack/day79-scale-upgrade-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day79-pack/day79-scale-upgrade-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day79-pack/day79-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day79-pack/day79-scale-upgrade-plan.md").exists()
    assert (tmp_path / "artifacts/day79-pack/day79-enterprise-execution-ledger.json").exists()
    assert (tmp_path / "artifacts/day79-pack/day79-enterprise-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day79-pack/day79-execution-log.md").exists()
    assert (tmp_path / "artifacts/day79-pack/day79-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day79-pack/day79-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day79-pack/evidence/day79-execution-summary.json").exists()


def test_day79_strict_fails_without_day78(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day78-ecosystem-priorities-closeout-pack/day78-ecosystem-priorities-closeout-summary.json"
    ).unlink()
    assert d79.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day79_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day79-scale-upgrade-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 79 scale upgrade closeout summary" in capsys.readouterr().out
