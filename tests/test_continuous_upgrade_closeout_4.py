from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import continuous_upgrade_closeout_4 as c4


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-continuous-upgrade-closeout-4.md\ncontinuous-upgrade-closeout-4\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "integrations-continuous-upgrade-closeout-4.md\nartifacts/continuous-upgrade-closeout-4-pack/continuous-upgrade-closeout-4-summary.json\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Cycle 3 — Continuous upgrade closeout lane:** close Cycle 3 continuous-upgrade quality loop.\n"
        "- **Cycle 4 — Continuous upgrade closeout lane:** start next-impact continuous upgrade execution.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-continuous-upgrade-closeout-4.md").write_text(
        c4._CYCLE4_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/cycle-4-big-upgrade-report.md").write_text("# Cycle 4 report\n", encoding="utf-8")
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/check_continuous_upgrade_contract_4.py").write_text(
        "from __future__ import annotations\n\nif __name__ == 'main_':\n    raise SystemExit(0)\n",
        encoding="utf-8",
    )

    summary = (
        root
        / "docs/artifacts/continuous-upgrade-closeout-pack-3/continuous-upgrade-closeout-summary-3.json"
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
        / "docs/artifacts/continuous-upgrade-closeout-pack-3/continuous-upgrade-delivery-board-3.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Cycle 3 delivery board",
                "- [ ] Cycle 3 evidence brief committed",
                "- [ ] Cycle 3 continuous upgrade plan committed",
                "- [ ] Cycle 3 upgrade template upgrade ledger exported",
                "- [ ] Cycle 3 storyline outcomes ledger exported",
                "- [ ] Next-impact roadmap draft captured from cycle 3 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/continuous-upgrade-plan-4.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "continuous-upgrade-cycle4-001",
                "contributors": ["maintainers", "release-ops"],
                "upgrade_channels": ["readme", "docs-index", "cli-lanes"],
                "baseline": {"strict_pass_rate": 0.9, "doc_link_coverage": 0.88},
                "target": {"strict_pass_rate": 1.0, "doc_link_coverage": 0.97},
                "owner": "release-ops",
                "rollback_owner": "incident-ops",
                "confidence_floor": 0.9,
                "cadence_interval": 7,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = c4.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "continuous-upgrade-closeout-4"
    assert out["summary"]["activation_score"] >= 95


def test_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = c4.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/continuous-upgrade-closeout-4-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/continuous-upgrade-closeout-4-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-closeout-4-pack/continuous-upgrade-closeout-4-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-closeout-4-pack/continuous-upgrade-closeout-4-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-closeout-4-pack/continuous-upgrade-cycle4-evidence-brief.md"
    ).exists()
    assert (
        tmp_path / "artifacts/continuous-upgrade-closeout-4-pack/continuous-upgrade-cycle4-plan.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-closeout-4-pack/continuous-upgrade-cycle4-upgrade-template-upgrade-ledger.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-closeout-4-pack/continuous-upgrade-cycle4-storyline-outcomes-ledger.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-closeout-4-pack/continuous-upgrade-cycle4-upgrade-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-closeout-4-pack/continuous-upgrade-cycle4-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-closeout-4-pack/continuous-upgrade-cycle4-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/continuous-upgrade-closeout-4-pack/continuous-upgrade-cycle4-validation-commands.md"
    ).exists()
    execution_summary = (
        tmp_path
        / "artifacts/continuous-upgrade-closeout-4-pack/evidence/cycle4-execution-summary.json"
    )
    assert execution_summary.exists()
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 0
    assert execution_data["strict_pass"] is True


def test_execute_strict_fails_on_command_error(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    monkeypatch.setattr(c4, "_EXECUTION_COMMANDS", ['python -c "import sys; sys.exit(3)"'])
    rc = c4.main(
        [
            "--root",
            str(tmp_path),
            "--execute",
            "--evidence-dir",
            "artifacts/continuous-upgrade-closeout-4-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1
    execution_summary = (
        tmp_path
        / "artifacts/continuous-upgrade-closeout-4-pack/evidence/cycle4-execution-summary.json"
    )
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 1
    assert execution_data["strict_pass"] is False


def test_strict_fails_without_cycle3(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/continuous-upgrade-closeout-pack-3/continuous-upgrade-closeout-summary-3.json"
    ).unlink()
    assert c4.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["continuous-upgrade-closeout-4", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Cycle 4 continuous upgrade closeout summary" in capsys.readouterr().out
