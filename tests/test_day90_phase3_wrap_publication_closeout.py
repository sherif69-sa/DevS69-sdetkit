from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day90_phase3_wrap_publication_closeout as d90


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day90-phase3-wrap-publication-closeout.md\nday90-phase3-wrap-publication-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-90-big-upgrade-report.md\nintegrations-day90-phase3-wrap-publication-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 89 — Governance priorities closeout lane:** convert governance handoff outcomes into governance scale.\n"
        "- **Day 90 — Phase-3 wrap publication closeout lane:** scale governance scale into deterministic execution lanes.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day90-phase3-wrap-publication-closeout.md").write_text(
        d90._DAY90_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-90-big-upgrade-report.md").write_text("# Day 90 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day89-governance-scale-closeout-pack/day89-governance-scale-closeout-summary.json"
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
    board = root / "docs/artifacts/day89-governance-scale-closeout-pack/day89-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 89 delivery board",
                "- [ ] Day 89 evidence brief committed",
                "- [ ] Day 89 governance scale plan committed",
                "- [ ] Day 89 narrative template upgrade ledger exported",
                "- [ ] Day 89 storyline outcomes ledger exported",
                "- [ ] Day 90 governance scale drafted from Day 89 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / ".day90-phase3-wrap-publication-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day90-phase3-wrap-publication-001",
                "contributors": ["maintainers", "release-ops"],
                "narrative_channels": ["launch-brief", "release-report", "faq"],
                "baseline": {"launch_confidence": 0.64, "narrative_reuse": 0.42},
                "target": {"launch_confidence": 0.86, "narrative_reuse": 0.67},
                "owner": "release-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day90_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d90.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day90-phase3-wrap-publication-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day90_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d90.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day90-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day90-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day90-pack/day90-phase3-wrap-publication-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day90-pack/day90-phase3-wrap-publication-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day90-pack/day90-evidence-brief.md").exists()
    assert (tmp_path / "artifacts/day90-pack/day90-phase3-wrap-publication-plan.md").exists()
    assert (tmp_path / "artifacts/day90-pack/day90-narrative-template-upgrade-ledger.json").exists()
    assert (tmp_path / "artifacts/day90-pack/day90-storyline-outcomes-ledger.json").exists()
    assert (tmp_path / "artifacts/day90-pack/day90-narrative-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day90-pack/day90-execution-log.md").exists()
    assert (tmp_path / "artifacts/day90-pack/day90-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day90-pack/day90-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day90-pack/evidence/day90-execution-summary.json").exists()


def test_day90_strict_fails_without_day89(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day89-governance-scale-closeout-pack/day89-governance-scale-closeout-summary.json"
    ).unlink()
    assert d90.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day90_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day90-phase3-wrap-publication-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 90 phase-3 wrap publication closeout summary" in capsys.readouterr().out
