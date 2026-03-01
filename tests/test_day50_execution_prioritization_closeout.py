from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day50_execution_prioritization_closeout as d50


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day50-execution-prioritization-closeout.md\nday50-execution-prioritization-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-50-big-upgrade-report.md\nintegrations-day50-execution-prioritization-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 50 — Execution prioritization lock:** convert weekly-review wins into a deterministic execution board.\n"
        "- **Day 51 — Case snippet #1:** publish mini-case on reliability or quality gate value.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day50-execution-prioritization-closeout.md").write_text(
        d50._DAY50_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-50-big-upgrade-report.md").write_text("# Day 50 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day49-weekly-review-closeout-pack/day49-weekly-review-closeout-summary.json"
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
    board = root / "docs/artifacts/day49-weekly-review-closeout-pack/day49-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 49 delivery board",
                "- [ ] Day 49 weekly review brief committed",
                "- [ ] Day 49 priorities reviewed with owner + backup",
                "- [ ] Day 49 risk register exported",
                "- [ ] Day 49 KPI scorecard snapshot exported",
                "- [ ] Day 50 execution priorities drafted from Day 49 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day50_execution_prioritization_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d50.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day50-execution-prioritization-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day50_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d50.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day50-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day50-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day50-pack/day50-execution-prioritization-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day50-pack/day50-execution-prioritization-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day50-pack/day50-execution-prioritization-brief.md").exists()
    assert (tmp_path / "artifacts/day50-pack/day50-risk-register.csv").exists()
    assert (
        tmp_path / "artifacts/day50-pack/day50-execution-prioritization-kpi-scorecard.json"
    ).exists()
    assert (tmp_path / "artifacts/day50-pack/day50-execution-log.md").exists()
    assert (tmp_path / "artifacts/day50-pack/day50-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day50-pack/day50-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day50-pack/evidence/day50-execution-summary.json").exists()


def test_day50_strict_fails_when_day49_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day49-weekly-review-closeout-pack/day49-weekly-review-closeout-summary.json"
    ).unlink()
    rc = d50.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day50_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day50-execution-prioritization-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 50 execution prioritization closeout summary" in capsys.readouterr().out
