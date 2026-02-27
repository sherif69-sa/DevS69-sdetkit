from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day82_integration_feedback_closeout as d82


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day82-integration-feedback-closeout.md\nday82-integration-feedback-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-82-big-upgrade-report.md\nintegrations-day82-integration-feedback-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 81 — Growth campaign closeout:** convert partner outcomes into deterministic campaign controls.\n"
        "- **Day 82 — Integration feedback loop:** fold field feedback into docs/templates.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day82-integration-feedback-closeout.md").write_text(
        d82._DAY82_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-82-big-upgrade-report.md").write_text("# Day 82 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day81-growth-campaign-closeout-pack/day81-growth-campaign-closeout-summary.json"
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
    board = root / "docs/artifacts/day81-growth-campaign-closeout-pack/day81-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 81 delivery board",
                "- [ ] Day 81 integration brief committed",
                "- [ ] Day 81 growth campaign plan committed",
                "- [ ] Day 81 campaign execution ledger exported",
                "- [ ] Day 81 campaign KPI scorecard snapshot exported",
                "- [ ] Day 82 execution priorities drafted from Day 81 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / ".day82-integration-feedback-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day82-integration-feedback-001",
                "contributors": ["maintainers", "docs-ops"],
                "feedback_channels": ["office-hours", "issues"],
                "baseline": {"feedback_items": 24, "docs_resolution_rate": 0.58},
                "target": {"feedback_items": 40, "docs_resolution_rate": 0.75},
                "owner": "docs-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day82_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d82.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day82-integration-feedback-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day82_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d82.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day82-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day82-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day82-pack/day82-integration-feedback-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day82-pack/day82-integration-feedback-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day82-pack/day82-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day82-pack/day82-integration-feedback-plan.md").exists()
    assert (tmp_path / "artifacts/day82-pack/day82-template-upgrade-ledger.json").exists()
    assert (tmp_path / "artifacts/day82-pack/day82-office-hours-outcomes-ledger.json").exists()
    assert (tmp_path / "artifacts/day82-pack/day82-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day82-pack/day82-execution-log.md").exists()
    assert (tmp_path / "artifacts/day82-pack/day82-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day82-pack/day82-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day82-pack/evidence/day82-execution-summary.json").exists()


def test_day82_strict_fails_without_day81(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day81-growth-campaign-closeout-pack/day81-growth-campaign-closeout-summary.json"
    ).unlink()
    assert d82.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day82_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day82-integration-feedback-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 82 integration feedback closeout summary" in capsys.readouterr().out
