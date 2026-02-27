from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day87_governance_handoff_closeout as d87


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day87-governance-handoff-closeout.md\nday87-governance-handoff-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-87-big-upgrade-report.md\nintegrations-day87-governance-handoff-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 86 — Launch readiness closeout lane:** convert launch readiness outcomes into governance ownership scorecards.\n"
        "- **Day 87 — Governance handoff closeout lane:** convert launch readiness outcomes into governance ownership scorecards.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day87-governance-handoff-closeout.md").write_text(
        d87._DAY87_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-87-big-upgrade-report.md").write_text("# Day 87 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day86-launch-readiness-closeout-pack/day86-launch-readiness-closeout-summary.json"
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
    board = root / "docs/artifacts/day86-launch-readiness-closeout-pack/day86-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 86 delivery board",
                "- [ ] Day 86 evidence brief committed",
                "- [ ] Day 86 launch readiness plan committed",
                "- [ ] Day 86 narrative template upgrade ledger exported",
                "- [ ] Day 86 storyline outcomes ledger exported",
                "- [ ] Day 87 governance priorities drafted from Day 86 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / ".day87-governance-handoff-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day87-governance-handoff-001",
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


def test_day87_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d87.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day87-governance-handoff-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day87_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d87.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day87-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day87-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day87-pack/day87-governance-handoff-closeout-summary.json"
    ).exists()
    assert (tmp_path / "artifacts/day87-pack/day87-governance-handoff-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day87-pack/day87-evidence-brief.md").exists()
    assert (tmp_path / "artifacts/day87-pack/day87-governance-handoff-plan.md").exists()
    assert (tmp_path / "artifacts/day87-pack/day87-narrative-template-upgrade-ledger.json").exists()
    assert (tmp_path / "artifacts/day87-pack/day87-storyline-outcomes-ledger.json").exists()
    assert (tmp_path / "artifacts/day87-pack/day87-narrative-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day87-pack/day87-execution-log.md").exists()
    assert (tmp_path / "artifacts/day87-pack/day87-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day87-pack/day87-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day87-pack/evidence/day87-execution-summary.json").exists()


def test_day87_strict_fails_without_day86(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day86-launch-readiness-closeout-pack/day86-launch-readiness-closeout-summary.json"
    ).unlink()
    assert d87.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day87_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day87-governance-handoff-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 87 governance handoff closeout summary" in capsys.readouterr().out
