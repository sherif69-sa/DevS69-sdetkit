from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day88_governance_priorities_closeout as d88


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day88-governance-priorities-closeout.md\nday88-governance-priorities-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-88-big-upgrade-report.md\nintegrations-day88-governance-priorities-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 87 — Launch readiness closeout lane:** convert launch readiness outcomes into governance ownership scorecards.\n"
        "- **Day 88 — Governance priorities closeout lane:** convert governance handoff outcomes into governed roadmap priorities.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day88-governance-priorities-closeout.md").write_text(
        d88._DAY88_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-88-big-upgrade-report.md").write_text("# Day 88 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day87-governance-handoff-closeout-pack/day87-governance-handoff-closeout-summary.json"
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
    board = root / "docs/artifacts/day87-governance-handoff-closeout-pack/day87-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 87 delivery board",
                "- [ ] Day 87 evidence brief committed",
                "- [ ] Day 87 governance handoff plan committed",
                "- [ ] Day 87 narrative template upgrade ledger exported",
                "- [ ] Day 87 storyline outcomes ledger exported",
                "- [ ] Day 89 governance priorities drafted from Day 88 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / ".day88-governance-priorities-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day88-governance-priorities-001",
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


def test_day88_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d88.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day88-governance-priorities-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day88_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d88.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day88-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day88-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day88-pack/day88-governance-priorities-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day88-pack/day88-governance-priorities-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day88-pack/day88-evidence-brief.md").exists()
    assert (tmp_path / "artifacts/day88-pack/day88-governance-priorities-plan.md").exists()
    assert (tmp_path / "artifacts/day88-pack/day88-narrative-template-upgrade-ledger.json").exists()
    assert (tmp_path / "artifacts/day88-pack/day88-storyline-outcomes-ledger.json").exists()
    assert (tmp_path / "artifacts/day88-pack/day88-narrative-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day88-pack/day88-execution-log.md").exists()
    assert (tmp_path / "artifacts/day88-pack/day88-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day88-pack/day88-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day88-pack/evidence/day88-execution-summary.json").exists()


def test_day88_strict_fails_without_day87(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day87-governance-handoff-closeout-pack/day87-governance-handoff-closeout-summary.json"
    ).unlink()
    assert d88.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day88_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day88-governance-priorities-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 88 governance priorities closeout summary" in capsys.readouterr().out
