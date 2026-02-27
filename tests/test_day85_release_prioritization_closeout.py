from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day85_release_prioritization_closeout as d85


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day85-release-prioritization-closeout.md\nday85-release-prioritization-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-85-big-upgrade-report.md\nintegrations-day85-release-prioritization-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 84 — Evidence narrative closeout lane:** convert field objections into deterministic trust upgrades.\n"
        "- **Day 85 — Release prioritization closeout lane:** convert trust outcomes into release-ready narrative proof packs.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day85-release-prioritization-closeout.md").write_text(
        d85._DAY85_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-85-big-upgrade-report.md").write_text("# Day 85 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day84-evidence-narrative-closeout-pack/day84-evidence-narrative-closeout-summary.json"
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
    board = root / "docs/artifacts/day84-evidence-narrative-closeout-pack/day84-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 84 delivery board",
                "- [ ] Day 84 evidence brief committed",
                "- [ ] Day 84 evidence narrative plan committed",
                "- [ ] Day 84 narrative template upgrade ledger exported",
                "- [ ] Day 84 storyline outcomes ledger exported",
                "- [ ] Day 85 release priorities drafted from Day 84 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / ".day85-release-prioritization-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day85-release-prioritization-001",
                "contributors": ["maintainers", "docs-ops"],
                "narrative_channels": ["release-report", "runbook", "faq"],
                "baseline": {"evidence_coverage": 0.64, "narrative_reuse": 0.42},
                "target": {"evidence_coverage": 0.86, "narrative_reuse": 0.67},
                "owner": "docs-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day85_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d85.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day85-release-prioritization-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day85_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d85.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day85-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day85-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day85-pack/day85-release-prioritization-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day85-pack/day85-release-prioritization-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day85-pack/day85-evidence-brief.md").exists()
    assert (tmp_path / "artifacts/day85-pack/day85-release-prioritization-plan.md").exists()
    assert (tmp_path / "artifacts/day85-pack/day85-narrative-template-upgrade-ledger.json").exists()
    assert (tmp_path / "artifacts/day85-pack/day85-storyline-outcomes-ledger.json").exists()
    assert (tmp_path / "artifacts/day85-pack/day85-narrative-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day85-pack/day85-execution-log.md").exists()
    assert (tmp_path / "artifacts/day85-pack/day85-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day85-pack/day85-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day85-pack/evidence/day85-execution-summary.json").exists()


def test_day85_strict_fails_without_day84(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day84-evidence-narrative-closeout-pack/day84-evidence-narrative-closeout-summary.json"
    ).unlink()
    assert d85.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day85_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day85-release-prioritization-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 85 release prioritization closeout summary" in capsys.readouterr().out
