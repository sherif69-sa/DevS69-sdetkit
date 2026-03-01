from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day41_expansion_automation as d41


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day41-expansion-automation.md\nday41-expansion-automation\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-41-big-upgrade-report.md\nintegrations-day41-expansion-automation.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 41 — Expansion automation lane:** automate scale winners into repeatable workflows.\n"
        "- **Day 42 — Optimization lane kickoff:** convert Day 41 execution into optimization loops.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day41-expansion-automation.md").write_text(
        d41._DAY41_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-41-big-upgrade-report.md").write_text("# Day 41 report\n", encoding="utf-8")

    summary = root / "docs/artifacts/day40-scale-lane-pack/day40-scale-lane-summary.json"
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
    board = root / "docs/artifacts/day40-scale-lane-pack/day40-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 40 delivery board",
                "- [ ] Day 40 scale plan draft committed",
                "- [ ] Day 40 review notes captured with owner + backup",
                "- [ ] Day 40 rollout timeline exported",
                "- [ ] Day 40 KPI scorecard snapshot exported",
                "- [ ] Day 41 expansion priorities drafted from Day 40 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day41_expansion_automation_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d41.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day41-expansion-automation"
    assert out["summary"]["activation_score"] >= 95


def test_day41_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d41.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day41-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day41-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day41-pack/day41-expansion-automation-summary.json").exists()
    assert (tmp_path / "artifacts/day41-pack/day41-expansion-automation-summary.md").exists()
    assert (tmp_path / "artifacts/day41-pack/day41-expansion-plan.md").exists()
    assert (tmp_path / "artifacts/day41-pack/day41-automation-matrix.csv").exists()
    assert (tmp_path / "artifacts/day41-pack/day41-expansion-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day41-pack/day41-execution-log.md").exists()
    assert (tmp_path / "artifacts/day41-pack/day41-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day41-pack/day41-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day41-pack/evidence/day41-execution-summary.json").exists()


def test_day41_strict_fails_when_day40_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day40-scale-lane-pack/day40-scale-lane-summary.json").unlink()
    rc = d41.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day41_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day41-expansion-automation", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 41 expansion automation summary" in capsys.readouterr().out
