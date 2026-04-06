from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import expansion_automation_41 as d41


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-expansion-automation.md\nexpansion-automation\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-41-big-upgrade-report.md\nintegrations-expansion-automation.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Expansion automation lane:** automate scale winners into repeatable workflows.\n"
        "- ** — Optimization lane kickoff:** convert  execution into optimization loops.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-expansion-automation.md").write_text(
        d41._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-41-big-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = root / "docs/artifacts/scale-lane-pack/scale-lane-summary.json"
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
    board = root / "docs/artifacts/scale-lane-pack/delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  scale plan draft committed",
                "- [ ]  review notes captured with owner + backup",
                "- [ ]  rollout timeline exported",
                "- [ ]  KPI scorecard snapshot exported",
                "- [ ]  expansion priorities drafted from  learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane41_expansion_automation_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d41.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "expansion-automation"
    assert out["summary"]["activation_score"] >= 95


def test_lane41_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d41.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/expansion-automation-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/expansion-automation-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/expansion-automation-pack/expansion-automation-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/expansion-automation-pack/expansion-automation-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/expansion-automation-pack/expansion-plan.md").exists()
    assert (tmp_path / "artifacts/expansion-automation-pack/automation-matrix.csv").exists()
    assert (tmp_path / "artifacts/expansion-automation-pack/expansion-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/expansion-automation-pack/execution-log.md").exists()
    assert (tmp_path / "artifacts/expansion-automation-pack/delivery-board.md").exists()
    assert (tmp_path / "artifacts/expansion-automation-pack/validation-commands.md").exists()
    assert (
        tmp_path / "artifacts/expansion-automation-pack/evidence/execution-summary.json"
    ).exists()


def test_lane41_strict_fails_when_lane40_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/scale-lane-pack/scale-lane-summary.json").unlink()
    rc = d41.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_lane41_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["expansion-automation", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Expansion automation summary" in capsys.readouterr().out
