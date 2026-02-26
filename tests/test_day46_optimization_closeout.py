from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day46_optimization_closeout as d46


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day46-optimization-closeout.md\nday46-optimization-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-46-big-upgrade-report.md\nintegrations-day46-optimization-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 46 — Optimization lane continuation:** convert Day 45 expansion wins into optimization plays.\n"
        "- **Day 47 — Reliability lane continuation:** convert Day 46 optimization wins into reliability plays.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day46-optimization-closeout.md").write_text(d46._DAY46_DEFAULT_PAGE, encoding="utf-8")
    (root / "docs/day-46-big-upgrade-report.md").write_text("# Day 46 report\n", encoding="utf-8")

    summary = root / "docs/artifacts/day45-expansion-closeout-pack/day45-expansion-closeout-summary.json"
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
    board = root / "docs/artifacts/day45-expansion-closeout-pack/day45-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 45 delivery board",
                "- [ ] Day 45 expansion plan draft committed",
                "- [ ] Day 45 review notes captured with owner + backup",
                "- [ ] Day 45 growth matrix exported",
                "- [ ] Day 45 KPI scorecard snapshot exported",
                "- [ ] Day 46 optimization priorities drafted from Day 45 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day46_optimization_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d46.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day46-optimization-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day46_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d46.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day46-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day46-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day46-pack/day46-optimization-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day46-pack/day46-optimization-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day46-pack/day46-optimization-plan.md").exists()
    assert (tmp_path / "artifacts/day46-pack/day46-bottleneck-map.csv").exists()
    assert (tmp_path / "artifacts/day46-pack/day46-optimization-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day46-pack/day46-execution-log.md").exists()
    assert (tmp_path / "artifacts/day46-pack/day46-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day46-pack/day46-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day46-pack/evidence/day46-execution-summary.json").exists()


def test_day46_strict_fails_when_day45_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day45-expansion-closeout-pack/day45-expansion-closeout-summary.json").unlink()
    rc = d46.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day46_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day46-optimization-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 46 optimization closeout summary" in capsys.readouterr().out
