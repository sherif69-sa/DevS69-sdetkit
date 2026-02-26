from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day45_expansion_closeout as d45


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day45-expansion-closeout.md\nday45-expansion-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-45-big-upgrade-report.md\nintegrations-day45-expansion-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 45 — Expansion closeout lane:** convert Day 44 scale proof into deterministic expansion loops.\n"
        "- **Day 46 — Optimization lane continuation:** convert Day 45 expansion wins into optimization plays.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day45-expansion-closeout.md").write_text(
        d45._DAY45_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-45-big-upgrade-report.md").write_text("# Day 45 report\n", encoding="utf-8")

    summary = root / "docs/artifacts/day44-scale-closeout-pack/day44-scale-closeout-summary.json"
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
    board = root / "docs/artifacts/day44-scale-closeout-pack/day44-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 44 delivery board",
                "- [ ] Day 44 scale plan draft committed",
                "- [ ] Day 44 review notes captured with owner + backup",
                "- [ ] Day 44 growth matrix exported",
                "- [ ] Day 44 KPI scorecard snapshot exported",
                "- [ ] Day 45 expansion priorities drafted from Day 44 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day45_expansion_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d45.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day45-expansion-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day45_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d45.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day45-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day45-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day45-pack/day45-expansion-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day45-pack/day45-expansion-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day45-pack/day45-expansion-plan.md").exists()
    assert (tmp_path / "artifacts/day45-pack/day45-growth-matrix.csv").exists()
    assert (tmp_path / "artifacts/day45-pack/day45-expansion-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day45-pack/day45-execution-log.md").exists()
    assert (tmp_path / "artifacts/day45-pack/day45-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day45-pack/day45-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day45-pack/evidence/day45-execution-summary.json").exists()


def test_day45_strict_fails_when_day44_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path / "docs/artifacts/day44-scale-closeout-pack/day44-scale-closeout-summary.json"
    ).unlink()
    rc = d45.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day45_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day45-expansion-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 45 expansion closeout summary" in capsys.readouterr().out
