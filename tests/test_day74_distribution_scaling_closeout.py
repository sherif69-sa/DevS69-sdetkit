from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day74_distribution_scaling_closeout as d74


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day74-distribution-scaling-closeout.md\nday74-distribution-scaling-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-74-big-upgrade-report.md\nintegrations-day74-distribution-scaling-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 74 — Distribution scaling:** convert Day 73 learnings into scaled channel operations.\n"
        "- **Day 75 — Trust assets refresh:** turn Day 74 outcomes into governance-grade trust proof.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day74-distribution-scaling-closeout.md").write_text(
        d74._DAY74_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-74-big-upgrade-report.md").write_text("# Day 74 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day73-case-study-launch-closeout-pack/day73-case-study-launch-closeout-summary.json"
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
    board = root / "docs/artifacts/day73-case-study-launch-closeout-pack/day73-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 73 delivery board",
                "- [ ] Day 73 integration brief committed",
                "- [ ] Day 73 published case-study narrative committed",
                "- [ ] Day 73 controls and assumptions log exported",
                "- [ ] Day 73 KPI scorecard snapshot exported",
                "- [ ] Day 74 distribution scaling priorities drafted from Day 73 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scaling_plan = root / ".day74-distribution-scaling-plan.json"
    scaling_plan.write_text(
        json.dumps(
            {
                "plan_id": "day74-distribution-scaling-001",
                "channels": ["github", "linkedin", "newsletter"],
                "baseline": {"qualified_leads": 22, "ctr": 0.038},
                "target": {"qualified_leads": 35, "ctr": 0.051},
                "confidence": 0.9,
                "owner": "growth-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day74_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d74.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day74-distribution-scaling-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day74_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d74.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day74-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day74-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day74-pack/day74-distribution-scaling-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day74-pack/day74-distribution-scaling-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day74-pack/day74-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day74-pack/day74-distribution-scaling-plan.md").exists()
    assert (tmp_path / "artifacts/day74-pack/day74-channel-controls-log.json").exists()
    assert (tmp_path / "artifacts/day74-pack/day74-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day74-pack/day74-execution-log.md").exists()
    assert (tmp_path / "artifacts/day74-pack/day74-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day74-pack/day74-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day74-pack/evidence/day74-execution-summary.json").exists()


def test_day74_strict_fails_without_day73(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day73-case-study-launch-closeout-pack/day73-case-study-launch-closeout-summary.json"
    ).unlink()
    assert d74.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day74_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day74-distribution-scaling-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 74 distribution scaling closeout summary" in capsys.readouterr().out
