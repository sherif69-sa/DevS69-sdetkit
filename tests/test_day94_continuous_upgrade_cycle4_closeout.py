from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day94_continuous_upgrade_cycle4_closeout as d93


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day94-continuous-upgrade-cycle4-closeout.md\nday94-continuous-upgrade-cycle4-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-94-big-upgrade-report.md\nintegrations-day94-continuous-upgrade-cycle4-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 93 — Continuous upgrade closeout lane:** close Day 93 continuous-upgrade quality loop.\n"
        "- **Day 94 — Continuous upgrade closeout lane:** start next-cycle continuous upgrade execution.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day94-continuous-upgrade-cycle4-closeout.md").write_text(
        d93._DAY94_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-94-big-upgrade-report.md").write_text("# Day 94 report\n", encoding="utf-8")
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/check_day94_continuous_upgrade_cycle4_closeout_contract.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(0)\n",
        encoding="utf-8",
    )

    summary = (
        root
        / "docs/artifacts/day93-continuous-upgrade-cycle3-closeout-pack/day93-continuous-upgrade-cycle3-closeout-summary.json"
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
        / "docs/artifacts/day93-continuous-upgrade-cycle3-closeout-pack/day93-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 93 delivery board",
                "- [ ] Day 93 evidence brief committed",
                "- [ ] Day 93 continuous upgrade plan committed",
                "- [ ] Day 93 upgrade template upgrade ledger exported",
                "- [ ] Day 93 storyline outcomes ledger exported",
                "- [ ] Next-cycle roadmap draft captured from Day 93 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/day94-continuous-upgrade-cycle4-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day94-continuous-upgrade-001",
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


def test_day94_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d93.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day94-continuous-upgrade-cycle4-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day94_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d93.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day94-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day94-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day94-pack/day94-continuous-upgrade-cycle4-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day94-pack/day94-continuous-upgrade-cycle4-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day94-pack/day94-evidence-brief.md").exists()
    assert (tmp_path / "artifacts/day94-pack/day94-continuous-upgrade-plan.md").exists()
    assert (tmp_path / "artifacts/day94-pack/day94-upgrade-template-upgrade-ledger.json").exists()
    assert (tmp_path / "artifacts/day94-pack/day94-storyline-outcomes-ledger.json").exists()
    assert (tmp_path / "artifacts/day94-pack/day94-upgrade-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day94-pack/day94-execution-log.md").exists()
    assert (tmp_path / "artifacts/day94-pack/day94-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day94-pack/day94-validation-commands.md").exists()
    execution_summary = tmp_path / "artifacts/day94-pack/evidence/day94-execution-summary.json"
    assert execution_summary.exists()
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 0
    assert execution_data["strict_pass"] is True


def test_day94_execute_strict_fails_on_command_error(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    monkeypatch.setattr(d93, "_EXECUTION_COMMANDS", ['python -c "import sys; sys.exit(3)"'])
    rc = d93.main(
        [
            "--root",
            str(tmp_path),
            "--execute",
            "--evidence-dir",
            "artifacts/day94-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1
    execution_summary = tmp_path / "artifacts/day94-pack/evidence/day94-execution-summary.json"
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 1
    assert execution_data["strict_pass"] is False


def test_day94_strict_fails_without_day93(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day93-continuous-upgrade-cycle3-closeout-pack/day93-continuous-upgrade-cycle3-closeout-summary.json"
    ).unlink()
    assert d93.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day94_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day94-continuous-upgrade-cycle4-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 94 continuous upgrade closeout summary" in capsys.readouterr().out
