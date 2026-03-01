from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day42_optimization_closeout as d42


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day42-optimization-closeout.md\nday42-optimization-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-42-big-upgrade-report.md\nintegrations-day42-optimization-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 42 — Optimization closeout lane:** convert Day 41 evidence into deterministic remediation loops.\n"
        "- **Day 43 — Acceleration lane kickoff:** scale Day 42 optimizations into repeatable growth plays.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day42-optimization-closeout.md").write_text(
        d42._DAY42_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-42-big-upgrade-report.md").write_text("# Day 42 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day41-expansion-automation-pack/day41-expansion-automation-summary.json"
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
    board = root / "docs/artifacts/day41-expansion-automation-pack/day41-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 41 delivery board",
                "- [ ] Day 41 expansion plan draft committed",
                "- [ ] Day 41 review notes captured with owner + backup",
                "- [ ] Day 41 automation matrix exported",
                "- [ ] Day 41 KPI scorecard snapshot exported",
                "- [ ] Day 42 optimization priorities drafted from Day 41 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day42_optimization_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d42.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day42-optimization-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day42_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d42.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day42-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day42-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day42-pack/day42-optimization-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day42-pack/day42-optimization-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day42-pack/day42-optimization-plan.md").exists()
    assert (tmp_path / "artifacts/day42-pack/day42-remediation-matrix.csv").exists()
    assert (tmp_path / "artifacts/day42-pack/day42-optimization-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day42-pack/day42-execution-log.md").exists()
    assert (tmp_path / "artifacts/day42-pack/day42-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day42-pack/day42-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day42-pack/evidence/day42-execution-summary.json").exists()


def test_day42_strict_fails_when_day41_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day41-expansion-automation-pack/day41-expansion-automation-summary.json"
    ).unlink()
    rc = d42.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day42_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day42-optimization-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 42 optimization closeout summary" in capsys.readouterr().out
