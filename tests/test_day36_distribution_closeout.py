from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day36_distribution_closeout as d36


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day36-distribution-closeout.md\nday36-distribution-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-36-big-upgrade-report.md\nintegrations-day36-distribution-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 36 — Distribution closeout:** publish channel-ready Day 35 KPI narrative with owners and posting windows.\n"
        "- **Day 37 — Experiment lane:** convert Day 36 misses into controlled growth experiments.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day36-distribution-closeout.md").write_text(
        d36._DAY36_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-36-big-upgrade-report.md").write_text("# Day 36 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day35-kpi-instrumentation-pack/day35-kpi-instrumentation-summary.json"
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
    board = root / "docs/artifacts/day35-kpi-instrumentation-pack/day35-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 35 delivery board",
                "- [ ] Day 35 KPI dictionary committed",
                "- [ ] Day 35 dashboard snapshot exported",
                "- [ ] Day 35 alert policy reviewed with owner + backup",
                "- [ ] Day 36 distribution message references KPI shifts",
                "- [ ] Day 37 experiment backlog seeded from KPI misses",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day36_distribution_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d36.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day36-distribution-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day36_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d36.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day36-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day36-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day36-pack/day36-distribution-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day36-pack/day36-distribution-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day36-pack/day36-distribution-message-kit.md").exists()
    assert (tmp_path / "artifacts/day36-pack/day36-launch-plan.csv").exists()
    assert (tmp_path / "artifacts/day36-pack/day36-experiment-backlog.md").exists()
    assert (tmp_path / "artifacts/day36-pack/day36-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day36-pack/day36-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day36-pack/evidence/day36-execution-summary.json").exists()


def test_day36_strict_fails_when_day35_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day35-kpi-instrumentation-pack/day35-kpi-instrumentation-summary.json"
    ).unlink()
    rc = d36.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day36_strict_fails_when_day35_board_is_not_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day35-kpi-instrumentation-pack/day35-delivery-board.md").write_text(
        "- [ ] Day 36 distribution message references KPI shifts\n", encoding="utf-8"
    )
    rc = d36.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day36_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day36-distribution-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 36 community distribution summary" in capsys.readouterr().out
