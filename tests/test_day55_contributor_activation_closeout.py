from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day55_contributor_activation_closeout as d55


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day55-contributor-activation-closeout.md\nday55-contributor-activation-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-55-big-upgrade-report.md\nintegrations-day55-contributor-activation-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 55 — Contributor activation #2:** escalate repeat contributors into owner tracks.\n"
        "- **Day 56 — Stabilization lane:** enforce deterministic follow-through and verification.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day55-contributor-activation-closeout.md").write_text(
        d55._DAY55_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-55-big-upgrade-report.md").write_text("# Day 55 report\n", encoding="utf-8")

    summary = (
        root / "docs/artifacts/day53-docs-loop-closeout-pack/day53-docs-loop-closeout-summary.json"
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
    board = root / "docs/artifacts/day53-docs-loop-closeout-pack/day53-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 53 delivery board",
                "- [ ] Day 53 docs-loop brief committed",
                "- [ ] Day 53 docs-loop plan reviewed with owner + backup",
                "- [ ] Day 53 cross-link map exported",
                "- [ ] Day 53 KPI scorecard snapshot exported",
                "- [ ] Day 55 contributor activation priorities drafted from Day 53 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day55_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d55.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day55-contributor-activation-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day55_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d55.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day55-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day55-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day55-pack/day55-contributor-activation-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day55-pack/day55-contributor-activation-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day55-pack/day55-contributor-activation-brief.md").exists()
    assert (tmp_path / "artifacts/day55-pack/day55-contributor-ladder.csv").exists()
    assert (
        tmp_path / "artifacts/day55-pack/day55-contributor-activation-kpi-scorecard.json"
    ).exists()
    assert (tmp_path / "artifacts/day55-pack/day55-execution-log.md").exists()
    assert (tmp_path / "artifacts/day55-pack/day55-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day55-pack/day55-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day55-pack/evidence/day55-execution-summary.json").exists()


def test_day55_strict_fails_without_day53(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day53-docs-loop-closeout-pack/day53-docs-loop-closeout-summary.json"
    ).unlink()
    assert d55.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day55_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day55-contributor-activation-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 55 contributor activation closeout summary" in capsys.readouterr().out
