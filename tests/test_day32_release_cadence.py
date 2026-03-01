from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day32_release_cadence as d32


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day32-release-cadence.md\nday32-release-cadence\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-32-ultra-upgrade-report.md\nintegrations-day32-release-cadence.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 32 — Release cadence setup:** lock weekly release rhythm and changelog publication checklist.\n"
        "- **Day 33 — Demo asset #1:** produce/publish `doctor` workflow short video or GIF.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day32-release-cadence.md").write_text(
        d32._DAY32_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-32-ultra-upgrade-report.md").write_text("# Day 32 report\n", encoding="utf-8")

    summary = root / "docs/artifacts/day31-phase2-pack/day31-phase2-kickoff-summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 98, "strict_pass": True},
                "checks": [{"check_id": "ok", "passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/day31-phase2-pack/day31-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 31 delivery board",
                "- [ ] Day 31 baseline metrics snapshot emitted",
                "- [ ] Day 32 release cadence checklist drafted",
                "- [ ] Day 33 demo asset plan (doctor) assigned",
                "- [ ] Day 34 demo asset plan (repo audit) assigned",
                "- [ ] Day 35 weekly review preparation checklist ready",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day32_release_cadence_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d32.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day32-release-cadence"
    assert out["summary"]["activation_score"] >= 95


def test_day32_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d32.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day32-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day32-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day32-pack/day32-release-cadence-summary.json").exists()
    assert (tmp_path / "artifacts/day32-pack/day32-release-cadence-summary.md").exists()
    assert (tmp_path / "artifacts/day32-pack/day32-cadence-calendar.json").exists()
    assert (tmp_path / "artifacts/day32-pack/day32-changelog-template.md").exists()
    assert (tmp_path / "artifacts/day32-pack/day32-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day32-pack/day32-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day32-pack/evidence/day32-execution-summary.json").exists()


def test_day32_strict_fails_when_day31_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day31-phase2-pack/day31-phase2-kickoff-summary.json").unlink()
    rc = d32.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day32_strict_fails_when_day31_board_is_not_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day31-phase2-pack/day31-delivery-board.md").write_text(
        "- [ ] Day 32 release cadence checklist drafted\n", encoding="utf-8"
    )
    rc = d32.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day32_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day32-release-cadence", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 32 release cadence summary" in capsys.readouterr().out
