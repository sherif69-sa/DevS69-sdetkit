from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day92_continuous_upgrade_cycle2_closeout as d92


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day92-continuous-upgrade-cycle2-closeout.md\nday92-continuous-upgrade-cycle2-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-92-big-upgrade-report.md\nintegrations-day92-continuous-upgrade-cycle2-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 91 — Continuous upgrade closeout lane:** close Day 91 continuous-upgrade quality loop.\n"
        "- **Day 92 — Continuous upgrade closeout lane:** start next-cycle continuous upgrade execution.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day92-continuous-upgrade-cycle2-closeout.md").write_text(
        d92._DAY92_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-92-big-upgrade-report.md").write_text("# Day 92 report\n", encoding="utf-8")
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/check_day92_continuous_upgrade_cycle2_closeout_contract.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(0)\n",
        encoding="utf-8",
    )

    summary = (
        root
        / "docs/artifacts/day91-continuous-upgrade-closeout-pack/day91-continuous-upgrade-closeout-summary.json"
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
    board = root / "docs/artifacts/day91-continuous-upgrade-closeout-pack/day91-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 91 delivery board",
                "- [ ] Day 91 evidence brief committed",
                "- [ ] Day 91 continuous upgrade plan committed",
                "- [ ] Day 91 upgrade template upgrade ledger exported",
                "- [ ] Day 91 storyline outcomes ledger exported",
                "- [ ] Next-cycle roadmap draft captured from Day 91 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/day92-continuous-upgrade-cycle2-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day92-continuous-upgrade-001",
                "contributors": ["maintainers", "release-ops"],
                "upgrade_channels": ["readme", "docs-index", "cli-lanes"],
                "baseline": {"strict_pass_rate": 0.9, "doc_link_coverage": 0.88},
                "target": {"strict_pass_rate": 1.0, "doc_link_coverage": 0.97},
                "owner": "release-ops",
                "rollback_owner": "incident-ops",
                "confidence_floor": 0.9,
                "cadence_days": 7,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day92_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d92.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "continuous-upgrade-cycle2-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day92_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d92.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day92-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day92-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day92-pack/day92-continuous-upgrade-cycle2-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day92-pack/day92-continuous-upgrade-cycle2-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day92-pack/day92-evidence-brief.md").exists()
    assert (tmp_path / "artifacts/day92-pack/day92-continuous-upgrade-plan.md").exists()
    assert (tmp_path / "artifacts/day92-pack/day92-upgrade-template-upgrade-ledger.json").exists()
    assert (tmp_path / "artifacts/day92-pack/day92-storyline-outcomes-ledger.json").exists()
    assert (tmp_path / "artifacts/day92-pack/day92-upgrade-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day92-pack/day92-execution-log.md").exists()
    assert (tmp_path / "artifacts/day92-pack/day92-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day92-pack/day92-validation-commands.md").exists()
    execution_summary = tmp_path / "artifacts/day92-pack/evidence/day92-execution-summary.json"
    assert execution_summary.exists()
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 0
    assert execution_data["strict_pass"] is True


def test_day92_execute_strict_fails_on_command_error(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    monkeypatch.setattr(d92, "_EXECUTION_COMMANDS", ['python -c "import sys; sys.exit(3)"'])
    rc = d92.main(
        [
            "--root",
            str(tmp_path),
            "--execute",
            "--evidence-dir",
            "artifacts/day92-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1
    execution_summary = tmp_path / "artifacts/day92-pack/evidence/day92-execution-summary.json"
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 1
    assert execution_data["strict_pass"] is False


def test_day92_strict_fails_without_day91(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day91-continuous-upgrade-closeout-pack/day91-continuous-upgrade-closeout-summary.json"
    ).unlink()
    assert d92.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day92_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["continuous-upgrade-cycle2-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 92 continuous upgrade closeout summary" in capsys.readouterr().out
