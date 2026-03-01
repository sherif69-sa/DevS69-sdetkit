from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day37_experiment_lane as d37


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day37-experiment-lane.md\nday37-experiment-lane\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-37-big-upgrade-report.md\nintegrations-day37-experiment-lane.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 37 — Experiment lane activation:** seed controlled experiments from Day 36 distribution misses and KPI deltas.\n"
        "- **Day 38 — Distribution batch #1:** publish coordinated posts linking demo assets to docs.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day37-experiment-lane.md").write_text(
        d37._DAY37_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-37-big-upgrade-report.md").write_text("# Day 37 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day36-distribution-closeout-pack/day36-distribution-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 99, "strict_pass": True},
                "checks": [{"check_id": "ok", "passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/day36-distribution-closeout-pack/day36-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 36 delivery board",
                "- [ ] Day 36 launch plan committed",
                "- [ ] Day 36 message kit reviewed with owner + backup",
                "- [ ] Day 36 posting windows locked",
                "- [ ] Day 37 experiment backlog seeded from channel misses",
                "- [ ] Day 37 summary owner confirmed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day37_distribution_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d37.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day37-experiment-lane"
    assert out["summary"]["activation_score"] >= 95


def test_day37_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d37.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day37-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day37-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day37-pack/day37-experiment-lane-summary.json").exists()
    assert (tmp_path / "artifacts/day37-pack/day37-experiment-lane-summary.md").exists()
    assert (tmp_path / "artifacts/day37-pack/day37-experiment-matrix.csv").exists()
    assert (tmp_path / "artifacts/day37-pack/day37-hypothesis-brief.md").exists()
    assert (tmp_path / "artifacts/day37-pack/day37-experiment-scorecard.json").exists()
    assert (tmp_path / "artifacts/day37-pack/day37-decision-log.md").exists()
    assert (tmp_path / "artifacts/day37-pack/day37-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day37-pack/day37-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day37-pack/evidence/day37-execution-summary.json").exists()


def test_day37_strict_fails_when_day36_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day36-distribution-closeout-pack/day36-distribution-closeout-summary.json"
    ).unlink()
    rc = d37.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day37_strict_fails_when_day36_board_is_not_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path / "docs/artifacts/day36-distribution-closeout-pack/day36-delivery-board.md"
    ).write_text("- [ ] Day 37 experiment backlog seeded from channel misses\n", encoding="utf-8")
    rc = d37.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day37_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day37-experiment-lane", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 37 experiment lane summary" in capsys.readouterr().out
