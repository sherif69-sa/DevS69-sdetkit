from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day43_acceleration_closeout as d42


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day43-acceleration-closeout.md\nday43-acceleration-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-43-big-upgrade-report.md\nintegrations-day43-acceleration-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 43 — Acceleration closeout lane:** convert Day 42 evidence into deterministic growth loops.\n"
        "- **Day 44 — Scale lane continuation:** convert Day 43 acceleration wins into scale plays.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day43-acceleration-closeout.md").write_text(
        d42._DAY43_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-43-big-upgrade-report.md").write_text("# Day 43 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day42-optimization-closeout-pack/day42-optimization-closeout-summary.json"
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
    board = root / "docs/artifacts/day42-optimization-closeout-pack/day42-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 42 delivery board",
                "- [ ] Day 42 optimization plan draft committed",
                "- [ ] Day 42 review notes captured with owner + backup",
                "- [ ] Day 42 remediation matrix exported",
                "- [ ] Day 42 KPI scorecard snapshot exported",
                "- [ ] Day 43 acceleration priorities drafted from Day 42 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day43_acceleration_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d42.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day43-acceleration-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day43_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d42.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day43-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day43-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day43-pack/day43-acceleration-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day43-pack/day43-acceleration-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day43-pack/day43-acceleration-plan.md").exists()
    assert (tmp_path / "artifacts/day43-pack/day43-growth-matrix.csv").exists()
    assert (tmp_path / "artifacts/day43-pack/day43-acceleration-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day43-pack/day43-execution-log.md").exists()
    assert (tmp_path / "artifacts/day43-pack/day43-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day43-pack/day43-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day43-pack/evidence/day43-execution-summary.json").exists()


def test_day43_strict_fails_when_day42_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day42-optimization-closeout-pack/day42-optimization-closeout-summary.json"
    ).unlink()
    rc = d42.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day43_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day43-acceleration-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 43 acceleration closeout summary" in capsys.readouterr().out
