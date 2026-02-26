from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day40_scale_lane as d40


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day40-scale-lane.md\nday40-scale-lane\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-40-big-upgrade-report.md\nintegrations-day40-scale-lane.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 40 — Scale lane #1:** expand distribution and publication motion across channels.\n"
        "- **Day 41 — Expansion lane kickoff:** convert Day 40 outcomes into repeatable automation.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day40-scale-lane.md").write_text(
        d40._DAY40_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-40-big-upgrade-report.md").write_text("# Day 40 report\n", encoding="utf-8")

    summary = root / "docs/artifacts/day39-playbook-post-pack/day39-playbook-post-summary.json"
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
    board = root / "docs/artifacts/day39-playbook-post-pack/day39-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 39 delivery board",
                "- [ ] Day 39 playbook draft committed",
                "- [ ] Day 39 review notes captured with owner + backup",
                "- [ ] Day 39 rollout timeline exported",
                "- [ ] Day 39 KPI scorecard snapshot exported",
                "- [ ] Day 40 scale priorities drafted from Day 39 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day40_scale_lane_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d40.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day40-scale-lane"
    assert out["summary"]["activation_score"] >= 95


def test_day40_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d40.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day40-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day40-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day40-pack/day40-scale-lane-summary.json").exists()
    assert (tmp_path / "artifacts/day40-pack/day40-scale-lane-summary.md").exists()
    assert (tmp_path / "artifacts/day40-pack/day40-scale-plan.md").exists()
    assert (tmp_path / "artifacts/day40-pack/day40-channel-matrix.csv").exists()
    assert (tmp_path / "artifacts/day40-pack/day40-scale-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day40-pack/day40-execution-log.md").exists()
    assert (tmp_path / "artifacts/day40-pack/day40-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day40-pack/day40-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day40-pack/evidence/day40-execution-summary.json").exists()


def test_day40_strict_fails_when_day39_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day39-playbook-post-pack/day39-playbook-post-summary.json").unlink()
    rc = d40.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day40_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day40-scale-lane", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 40 scale lane summary" in capsys.readouterr().out
