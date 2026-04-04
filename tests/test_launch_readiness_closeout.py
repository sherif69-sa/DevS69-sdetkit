from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import launch_readiness_closeout_86 as d86


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-launch-readiness-closeout.md\nlaunch-readiness-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-86-big-upgrade-report.md\nintegrations-launch-readiness-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 85 — Release prioritization closeout lane:** convert trust outcomes into release-ready narrative proof packs.\n"
        "- **Day 86 — Launch readiness closeout lane:** convert release priorities into deterministic launch execution lanes.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-launch-readiness-closeout.md").write_text(
        d86._DAY86_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/impact-86-big-upgrade-report.md").write_text(
        "# Day 86 report\n", encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/release-prioritization-closeout-pack/release-prioritization-closeout-summary.json"
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
        / "docs/artifacts/release-prioritization-closeout-pack/release-prioritization-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 85 delivery board",
                "- [ ] Day 85 evidence brief committed",
                "- [ ] Day 85 release prioritization plan committed",
                "- [ ] Day 85 narrative template upgrade ledger exported",
                "- [ ] Day 85 storyline outcomes ledger exported",
                "- [ ] Day 86 launch priorities drafted from Day 85 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/launch-readiness-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "launch-readiness-001",
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


def test_lane86_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d86.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "launch-readiness-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane86_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d86.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/launch-readiness-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/launch-readiness-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/launch-readiness-pack/launch-readiness-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/launch-readiness-pack/launch-readiness-closeout-summary.md"
    ).exists()
    assert (
        tmp_path / "artifacts/launch-readiness-pack/launch-readiness-evidence-brief.md"
    ).exists()
    assert (tmp_path / "artifacts/launch-readiness-pack/launch-readiness-plan.md").exists()
    assert (
        tmp_path
        / "artifacts/launch-readiness-pack/launch-readiness-narrative-template-upgrade-ledger.json"
    ).exists()
    assert (
        tmp_path / "artifacts/launch-readiness-pack/launch-readiness-storyline-outcomes-ledger.json"
    ).exists()
    assert (
        tmp_path / "artifacts/launch-readiness-pack/launch-readiness-narrative-kpi-scorecard.json"
    ).exists()
    assert (tmp_path / "artifacts/launch-readiness-pack/launch-readiness-execution-log.md").exists()
    assert (
        tmp_path / "artifacts/launch-readiness-pack/launch-readiness-delivery-board.md"
    ).exists()
    assert (
        tmp_path / "artifacts/launch-readiness-pack/launch-readiness-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/launch-readiness-pack/evidence/launch-readiness-execution-summary.json"
    ).exists()


def test_lane86_strict_fails_without_day85(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/release-prioritization-closeout-pack/release-prioritization-closeout-summary.json"
    ).unlink()
    assert d86.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane86_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["launch-readiness-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 86 launch readiness closeout summary" in capsys.readouterr().out
