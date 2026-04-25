from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import trust_assets_refresh_closeout_75 as d75
from sdetkit.evidence import trust_assets_refresh_closeout_75 as d75_impl


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-trust-assets-refresh-closeout.md\ntrust-assets-refresh-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-75-big-upgrade-report.md\nintegrations-trust-assets-refresh-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Trust assets refresh:** turn  outcomes into governance-grade trust proof.\n"
        "- ** — Contributor recognition board:** publish contributor spotlight and release credits model.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-trust-assets-refresh-closeout.md").write_text(
        d75._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-75-big-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/distribution-scaling-closeout-pack/distribution-scaling-closeout-summary.json"
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
        / "docs/artifacts/distribution-scaling-closeout-pack/distribution-scaling-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  integration brief committed",
                "- [ ]  distribution scaling plan committed",
                "- [ ]  channel controls and assumptions log exported",
                "- [ ]  KPI scorecard snapshot exported",
                "- [ ]  trust refresh priorities drafted from  learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    trust_plan = root / "docs/roadmap/plans/trust-assets-refresh-plan.json"
    trust_plan.write_text(
        json.dumps(
            {
                "plan_id": "trust-assets-refresh-001",
                "trust_surfaces": ["README", "SECURITY", "governance"],
                "baseline": {"proof_links": 8, "policy_coverage": 0.67},
                "target": {"proof_links": 14, "policy_coverage": 0.9},
                "confidence": 0.9,
                "owner": "trust-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "scripts/check_trust_assets_refresh_closeout_contract.py").write_text(
        "from __future__ import annotations\n\n"
        "import sys\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(0)\n",
        encoding="utf-8",
    )


def test_lane75_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d75.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "trust-assets-refresh-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane75_default_template_has_no_unresolved_placeholders() -> None:
    assert "## Required inputs ()" not in d75._DEFAULT_PAGE_TEMPLATE
    assert "## Why  matters" not in d75._DEFAULT_PAGE_TEMPLATE
    assert "#  —" not in d75._DEFAULT_PAGE_TEMPLATE


def test_lane75_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d75.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/trust-assets-refresh-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/trust-assets-refresh-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-closeout-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-closeout-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-integration-brief.md"
    ).exists()
    assert (
        tmp_path / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-plan.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-trust-controls-log.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-trust-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/trust-assets-refresh-closeout-pack/evidence/trust-assets-refresh-execution-summary.json"
    ).exists()
    integration_brief = (
        tmp_path / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-integration-brief.md"
    ).read_text(encoding="utf-8")
    delivery_board = (
        tmp_path / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-delivery-board.md"
    ).read_text(encoding="utf-8")
    validation_commands = (
        tmp_path
        / "artifacts/trust-assets-refresh-closeout-pack/trust-assets-refresh-validation-commands.md"
    ).read_text(encoding="utf-8")
    assert "#  " not in integration_brief
    assert "#  " not in delivery_board
    assert "# Validation commands" in validation_commands
    for command in d75._EXECUTION_COMMANDS:
        assert command in validation_commands


def test_lane75_strict_fails_without_distribution_scaling_baseline(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/distribution-scaling-closeout-pack/distribution-scaling-closeout-summary.json"
    ).unlink()
    assert d75.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane75_board_anchor_is_enforced(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    board = (
        tmp_path
        / "docs/artifacts/distribution-scaling-closeout-pack/distribution-scaling-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ] Lane integration brief committed",
                "- [ ] Lane handoff notes captured",
                "- [ ] Lane channel controls and assumptions log exported",
                "- [ ] Lane KPI scorecard snapshot exported",
                "- [ ] Lane trust refresh priorities drafted from Lane learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert d75.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane75_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["trust-assets-refresh-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Trust Assets Refresh Closeout summary" in capsys.readouterr().out


def test_lane75_execute_failure_returns_nonzero_and_reports_failure(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _seed_repo(tmp_path)
    monkeypatch.setattr(
        d75_impl,
        "_EXECUTION_COMMANDS",
        ["python -c \"import sys; sys.exit(3)\""],
    )
    rc = d75.main(
        [
            "--root",
            str(tmp_path),
            "--execute",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["execution"]["failed_count"] == 1
    assert out["execution"]["failed_commands"] == [1]
