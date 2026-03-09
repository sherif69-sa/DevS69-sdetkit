from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day97_continuous_upgrade_cycle7_closeout as d93


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day97-continuous-upgrade-cycle7-closeout.md\nday97-continuous-upgrade-cycle7-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-97-big-upgrade-report.md\nintegrations-day97-continuous-upgrade-cycle7-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 95 — Continuous upgrade closeout lane:** close Day 95 continuous-upgrade quality loop.\n"
        "- **Day 97 — Continuous upgrade closeout lane:** start next-cycle continuous upgrade execution.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day97-continuous-upgrade-cycle7-closeout.md").write_text(
        d93._DAY95_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-97-big-upgrade-report.md").write_text("# Day 97 report\n", encoding="utf-8")
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/check_day97_continuous_upgrade_cycle7_closeout_contract.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(0)\n",
        encoding="utf-8",
    )

    summary = (
        root
        / "docs/artifacts/day95-continuous-upgrade-cycle5-closeout-pack/day95-continuous-upgrade-cycle5-closeout-summary.json"
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
    board = (
        root
        / "docs/artifacts/day95-continuous-upgrade-cycle5-closeout-pack/day95-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 95 delivery board",
                "- [ ] Day 95 evidence brief committed",
                "- [ ] Day 95 continuous upgrade plan committed",
                "- [ ] Day 95 upgrade template upgrade ledger exported",
                "- [ ] Day 95 storyline outcomes ledger exported",
                "- [ ] Next-cycle roadmap draft captured from Day 95 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/day97-continuous-upgrade-cycle7-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day97-continuous-upgrade-001",
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


def test_day95_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d93.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day97-continuous-upgrade-cycle7-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day97_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d93.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day97-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day97-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day97-pack/day97-continuous-upgrade-cycle7-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day97-pack/day97-continuous-upgrade-cycle7-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day97-pack/day97-evidence-brief.md").exists()
    assert (tmp_path / "artifacts/day97-pack/day97-continuous-upgrade-plan.md").exists()
    assert (tmp_path / "artifacts/day97-pack/day97-upgrade-template-upgrade-ledger.json").exists()
    assert (tmp_path / "artifacts/day97-pack/day97-storyline-outcomes-ledger.json").exists()
    assert (tmp_path / "artifacts/day97-pack/day97-upgrade-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day97-pack/day97-execution-log.md").exists()
    assert (tmp_path / "artifacts/day97-pack/day97-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day97-pack/day97-validation-commands.md").exists()
    execution_summary = tmp_path / "artifacts/day97-pack/evidence/day97-execution-summary.json"
    assert execution_summary.exists()
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 0
    assert execution_data["strict_pass"] is True


def test_day95_execute_strict_fails_on_command_error(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    monkeypatch.setattr(d93, "_EXECUTION_COMMANDS", ['python -c "import sys; sys.exit(3)"'])
    rc = d93.main(
        [
            "--root",
            str(tmp_path),
            "--execute",
            "--evidence-dir",
            "artifacts/day97-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1
    execution_summary = tmp_path / "artifacts/day97-pack/evidence/day97-execution-summary.json"
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 1
    assert execution_data["strict_pass"] is False


def test_day95_strict_fails_without_day93(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day95-continuous-upgrade-cycle5-closeout-pack/day95-continuous-upgrade-cycle5-closeout-summary.json"
    ).unlink()
    assert d93.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day95_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day97-continuous-upgrade-cycle7-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 97 continuous upgrade closeout summary" in capsys.readouterr().out
