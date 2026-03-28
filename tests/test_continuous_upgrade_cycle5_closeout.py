from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import continuous_upgrade_cycle5_closeout as c5


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-continuous-upgrade-cycle5-closeout.md\ncontinuous-upgrade-cycle5-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "integrations-continuous-upgrade-cycle5-closeout.md\nartifacts/continuous-upgrade-cycle5-closeout-pack/continuous-upgrade-cycle5-closeout-summary.json\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Cycle 4 — Continuous upgrade closeout lane:** close cycle 4 continuous-upgrade quality loop.\n"
        "- **Cycle 5 — Continuous upgrade closeout lane:** start next-impact continuous upgrade execution.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-continuous-upgrade-cycle5-closeout.md").write_text(
        c5._CYCLE5_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/cycle-5-big-upgrade-report.md").write_text("# Cycle 5 report\n", encoding="utf-8")
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/check_continuous_upgrade_cycle5_contract.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(0)\n",
        encoding="utf-8",
    )

    summary = (
        root
        / "docs/artifacts/continuous-upgrade-cycle4-closeout-pack/continuous-upgrade-cycle4-closeout-summary.json"
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
        / "docs/artifacts/continuous-upgrade-cycle4-closeout-pack/continuous-upgrade-cycle4-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Cycle 4 delivery board",
                "- [ ] Cycle 4 evidence brief committed",
                "- [ ] Cycle 4 continuous upgrade plan committed",
                "- [ ] Cycle 4 upgrade template upgrade ledger exported",
                "- [ ] Cycle 4 storyline outcomes ledger exported",
                "- [ ] Next-impact roadmap draft captured from cycle 4 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/continuous-upgrade-cycle5-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "continuous-upgrade-cycle5-001",
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


def test_cycle5_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = c5.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "continuous-upgrade-cycle5-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_cycle5_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = c5.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/continuous-upgrade-cycle5-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/continuous-upgrade-cycle5-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/continuous-upgrade-cycle5-closeout-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/continuous-upgrade-cycle5-closeout-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/continuous-upgrade-cycle5-evidence-brief.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/continuous-upgrade-cycle5-plan.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/continuous-upgrade-cycle5-upgrade-template-upgrade-ledger.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/continuous-upgrade-cycle5-storyline-outcomes-ledger.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/continuous-upgrade-cycle5-upgrade-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/continuous-upgrade-cycle5-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/continuous-upgrade-cycle5-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/continuous-upgrade-cycle5-validation-commands.md"
    ).exists()
    execution_summary = (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/evidence/cycle5-execution-summary.json"
    )
    assert execution_summary.exists()
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 0
    assert execution_data["strict_pass"] is True


def test_cycle5_execute_strict_fails_on_command_error(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    monkeypatch.setattr(c5, "_EXECUTION_COMMANDS", ['python -c "import sys; sys.exit(3)"'])
    rc = c5.main(
        [
            "--root",
            str(tmp_path),
            "--execute",
            "--evidence-dir",
            "artifacts/continuous-upgrade-cycle5-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1
    execution_summary = (
        tmp_path
        / "artifacts/continuous-upgrade-cycle5-closeout-pack/evidence/cycle5-execution-summary.json"
    )
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 1
    assert execution_data["strict_pass"] is False


def test_cycle5_strict_fails_without_cycle4(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/continuous-upgrade-cycle4-closeout-pack/continuous-upgrade-cycle4-closeout-summary.json"
    ).unlink()
    assert c5.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_cycle5_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["continuous-upgrade-cycle5-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Continuous upgrade cycle 5 closeout summary" in capsys.readouterr().out
