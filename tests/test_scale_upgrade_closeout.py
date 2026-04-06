from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import scale_upgrade_closeout_79 as d79


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-scale-upgrade-closeout.md\nscale-upgrade-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-79-big-upgrade-report.md\nintegrations-scale-upgrade-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "Ecosystem priorities + scale upgrade strategy chain\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-scale-upgrade-closeout.md").write_text(
        d79._DEFAULT_PAGE_TEMPLATE,
        encoding="utf-8",
    )

    summary = (
        root
        / "docs/artifacts/ecosystem-priorities-closeout-pack/ecosystem-priorities-closeout-summary.json"
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
        / "docs/artifacts/ecosystem-priorities-closeout-pack/ecosystem-priorities-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# delivery board",
                "- [ ] integration brief committed",
                "- [ ] ecosystem priorities plan committed",
                "- [ ] ecosystem workstream ledger exported",
                "- [ ] ecosystem KPI scorecard snapshot exported",
                "- [ ] partner outreach priorities drafted from learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scale_plan = root / "docs/roadmap/plans/scale-upgrade-plan.json"
    scale_plan.write_text(
        json.dumps(
            {
                "plan_id": "scale-upgrade-001",
                "contributors": ["maintainers", "enterprise-success"],
                "scale_tracks": ["role-based-onboarding", "control-plane-rollout"],
                "baseline": {"activated_orgs": 3, "setup_duration": 12},
                "target": {"activated_orgs": 6, "setup_duration": 7},
                "owner": "enterprise-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_lane79_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d79.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "scale-upgrade-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane79_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d79.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/scale-upgrade-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/scale-upgrade-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/scale-upgrade-pack/scale-upgrade-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/scale-upgrade-pack/scale-upgrade-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/scale-upgrade-pack/scale-upgrade-integration-brief.md").exists()
    assert (tmp_path / "artifacts/scale-upgrade-pack/scale-upgrade-plan.md").exists()
    assert (
        tmp_path / "artifacts/scale-upgrade-pack/scale-upgrade-enterprise-execution-ledger.json"
    ).exists()
    assert (
        tmp_path / "artifacts/scale-upgrade-pack/scale-upgrade-enterprise-kpi-scorecard.json"
    ).exists()
    assert (tmp_path / "artifacts/scale-upgrade-pack/scale-upgrade-execution-log.md").exists()
    assert (tmp_path / "artifacts/scale-upgrade-pack/scale-upgrade-delivery-board.md").exists()
    assert (tmp_path / "artifacts/scale-upgrade-pack/scale-upgrade-validation-commands.md").exists()
    assert (
        tmp_path / "artifacts/scale-upgrade-pack/evidence/scale-upgrade-execution-summary.json"
    ).exists()


def test_lane79_strict_fails_without_ecosystem_priorities_baseline(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/ecosystem-priorities-closeout-pack/ecosystem-priorities-closeout-summary.json"
    ).unlink()
    assert d79.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane79_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["scale-upgrade-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Scale Upgrade Closeout summary" in capsys.readouterr().out
