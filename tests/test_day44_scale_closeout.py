from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day44_scale_closeout as d44


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day44-scale-closeout.md\nday44-scale-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-44-big-upgrade-report.md\nintegrations-day44-scale-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 44 — Scale closeout lane:** convert Day 43 acceleration proof into deterministic scale loops.\n"
        "- **Day 45 — Expansion lane continuation:** convert Day 44 scale wins into expansion plays.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day44-scale-closeout.md").write_text(
        d44._DAY44_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-44-big-upgrade-report.md").write_text("# Day 44 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day43-acceleration-closeout-pack/day43-acceleration-closeout-summary.json"
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
    board = root / "docs/artifacts/day43-acceleration-closeout-pack/day43-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 43 delivery board",
                "- [ ] Day 43 acceleration plan draft committed",
                "- [ ] Day 43 review notes captured with owner + backup",
                "- [ ] Day 43 remediation matrix exported",
                "- [ ] Day 43 KPI scorecard snapshot exported",
                "- [ ] Day 44 scale priorities drafted from Day 43 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day44_scale_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d44.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day44-scale-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day44_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d44.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day44-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day44-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day44-pack/day44-scale-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day44-pack/day44-scale-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day44-pack/day44-scale-plan.md").exists()
    assert (tmp_path / "artifacts/day44-pack/day44-growth-matrix.csv").exists()
    assert (tmp_path / "artifacts/day44-pack/day44-scale-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day44-pack/day44-execution-log.md").exists()
    assert (tmp_path / "artifacts/day44-pack/day44-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day44-pack/day44-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day44-pack/evidence/day44-execution-summary.json").exists()


def test_day44_strict_fails_when_day43_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day43-acceleration-closeout-pack/day43-acceleration-closeout-summary.json"
    ).unlink()
    rc = d44.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day44_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day44-scale-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 44 scale closeout summary" in capsys.readouterr().out
