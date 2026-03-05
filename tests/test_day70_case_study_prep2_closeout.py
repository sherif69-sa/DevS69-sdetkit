from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day70_case_study_prep2_closeout as d70


def _seed_repo(root: Path) -> None:
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day70-case-study-prep2-closeout.md\nday70-case-study-prep2-closeout\n",
        encoding="utf-8",
    )
    (root / "docs/index.md").write_text(
        "day-70-big-upgrade-report.md\nintegrations-day70-case-study-prep2-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text("Day 70\nDay 71\n", encoding="utf-8")
    (root / "docs/integrations-day70-case-study-prep2-closeout.md").write_text(
        d70._DAY70_DEFAULT_PAGE, encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/day69-case-study-prep1-closeout-pack/day69-case-study-prep1-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 100, "strict_pass": True},
                "checks": [{"passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/day69-case-study-prep1-closeout-pack/day69-delivery-board.md"
    board.write_text(
        "\n".join(["# Day 69 delivery board", *["- [ ] Day 69 item" for _ in range(5)]]) + "\n",
        encoding="utf-8",
    )
    (root / "docs/roadmap/plans/day70-triage-speed-case-study.json").write_text(
        json.dumps(
            {
                "case_id": "day70-001",
                "metric": "triage-speed",
                "baseline": {"value": 41},
                "after": {"value": 19},
                "confidence": 0.92,
                "owner": "ops-quality",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day70_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d70.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day70-case-study-prep2-closeout"
    assert out["summary"]["strict_pass"] is True


def test_day70_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d70.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day70-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day70-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day70-pack/day70-case-study-prep2-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day70-pack/day70-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day70-pack/evidence/day70-execution-summary.json").exists()


def test_day70_strict_fails_without_day69_summary(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day69-case-study-prep1-closeout-pack/day69-case-study-prep1-closeout-summary.json"
    ).unlink()
    assert d70.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day70_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day70-case-study-prep2-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 70 case-study prep #2 closeout summary" in capsys.readouterr().out
