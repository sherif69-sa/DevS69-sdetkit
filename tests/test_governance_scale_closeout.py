from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import governance_scale_closeout_89 as d89


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-governance-scale-closeout.md\ngovernance-scale-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-89-big-upgrade-report.md\nintegrations-governance-scale-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 88 — Governance priorities closeout lane:** convert governance handoff outcomes into governance priorities.\n"
        "- **Day 89 — Governance scale closeout lane:** scale governance priorities into deterministic execution lanes.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-governance-scale-closeout.md").write_text(
        d89._DAY89_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/impact-89-big-upgrade-report.md").write_text(
        "# Day 89 report\n", encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/governance-priorities-closeout-pack/governance-priorities-closeout-summary.json"
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
        root / "docs/artifacts/governance-priorities-closeout-pack/governance-priorities-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 88 delivery board",
                "- [ ] Day 88 evidence brief committed",
                "- [ ] Day 88 governance priorities plan committed",
                "- [ ] Day 88 narrative template upgrade ledger exported",
                "- [ ] Day 88 storyline outcomes ledger exported",
                "- [ ] Day 89 governance priorities drafted from Day 88 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/governance-scale-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "governance-scale-001",
                "contributors": ["maintainers", "release-ops"],
                "narrative_channels": ["launch-brief", "release-report", "faq"],
                "baseline": {"launch_confidence": 0.64, "narrative_reuse": 0.42},
                "target": {"launch_confidence": 0.86, "narrative_reuse": 0.67},
                "owner": "release-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day89_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d89.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "governance-scale-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day89_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d89.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/governance-scale-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/governance-scale-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/governance-scale-pack/governance-scale-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/governance-scale-pack/governance-scale-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/governance-scale-pack/governance-scale-evidence-brief.md").exists()
    assert (tmp_path / "artifacts/governance-scale-pack/governance-scale-plan.md").exists()
    assert (tmp_path / "artifacts/governance-scale-pack/governance-scale-narrative-template-upgrade-ledger.json").exists()
    assert (tmp_path / "artifacts/governance-scale-pack/governance-scale-storyline-outcomes-ledger.json").exists()
    assert (tmp_path / "artifacts/governance-scale-pack/governance-scale-narrative-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/governance-scale-pack/governance-scale-execution-log.md").exists()
    assert (tmp_path / "artifacts/governance-scale-pack/governance-scale-delivery-board.md").exists()
    assert (tmp_path / "artifacts/governance-scale-pack/governance-scale-validation-commands.md").exists()
    assert (tmp_path / "artifacts/governance-scale-pack/evidence/governance-scale-execution-summary.json").exists()


def test_day89_strict_fails_without_day88(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/governance-priorities-closeout-pack/governance-priorities-closeout-summary.json"
    ).unlink()
    assert d89.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day89_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["governance-scale-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 89 governance scale closeout summary" in capsys.readouterr().out
