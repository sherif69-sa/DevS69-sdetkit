from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day63_onboarding_activation_closeout as d63


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day63-onboarding-activation-closeout.md\nday63-onboarding-activation-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-63-big-upgrade-report.md\nintegrations-day63-onboarding-activation-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 63 — Contributor onboarding activation:** launch orientation flow and ownership handoff loops.\n"
        "- **Day 64 — Integration expansion #1:** add advanced GitHub Actions reference workflow.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day63-onboarding-activation-closeout.md").write_text(
        d63._DAY63_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-63-big-upgrade-report.md").write_text("# Day 63 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day62-community-program-closeout-pack/day62-community-program-closeout-summary.json"
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
    board = root / "docs/artifacts/day62-community-program-closeout-pack/day62-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 62 delivery board",
                "- [ ] Day 62 community launch brief committed",
                "- [ ] Day 62 office-hours cadence published",
                "- [ ] Day 62 participation policy + moderation SOP exported",
                "- [ ] Day 62 KPI scorecard snapshot exported",
                "- [ ] Day 63 onboarding priorities drafted from Day 62 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day63_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d63.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day63-onboarding-activation-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day63_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d63.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day63-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day63-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day63-pack/day63-onboarding-activation-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day63-pack/day63-onboarding-activation-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day63-pack/day63-onboarding-launch-brief.md").exists()
    assert (tmp_path / "artifacts/day63-pack/day63-orientation-script.md").exists()
    assert (tmp_path / "artifacts/day63-pack/day63-ownership-matrix.csv").exists()
    assert (tmp_path / "artifacts/day63-pack/day63-roadmap-voting-brief.md").exists()
    assert (tmp_path / "artifacts/day63-pack/day63-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day63-pack/day63-execution-log.md").exists()
    assert (tmp_path / "artifacts/day63-pack/day63-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day63-pack/day63-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day63-pack/evidence/day63-execution-summary.json").exists()


def test_day63_strict_fails_without_day62(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day62-community-program-closeout-pack/day62-community-program-closeout-summary.json"
    ).unlink()
    assert d63.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day63_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day63-onboarding-activation-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 63 onboarding activation closeout summary" in capsys.readouterr().out
