from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import platform_readiness_kickoff as d61
from tests.workflow_fixture_seed import seed_contract_anchors


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-platform-readiness-kickoff-workflow.md\nplatform-readiness-kickoff-completion-report\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-61-big-upgrade-report.md\nintegrations-platform-readiness-kickoff-workflow.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — platform readiness kickoff:** set Platform readiness baseline and define ecosystem/trust KPIs.\n"
        "- ** — Community program setup:** publish office-hours cadence and participation rules.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-platform-readiness-kickoff-workflow.md").write_text(
        d61._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-61-big-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/release-readiness-wrap-handoff-completion-report-pack/release-readiness-wrap-handoff-completion-report-summary.json"
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
        / "docs/artifacts/release-readiness-wrap-handoff-completion-report-pack/release-readiness-wrap-handoff-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  release readiness wrap handoff brief committed",
                "- [ ]  wrap reviewed with owner + backup",
                "- [ ]  risk ledger exported",
                "- [ ]  KPI scorecard snapshot exported",
                "- [ ]  execution priorities drafted from  learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_phase3_kickoff_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d61.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "platform-readiness-kickoff-completion-report"
    assert out["summary"]["activation_score"] >= 95


def test_phase3_kickoff_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d61.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/platform-readiness-kickoff-completion-report-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/platform-readiness-kickoff-completion-report-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/platform-readiness-kickoff-completion-report-pack/platform-readiness-kickoff-completion-report-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-kickoff-completion-report-pack/platform-readiness-kickoff-completion-report-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-kickoff-completion-report-pack/platform-readiness-kickoff-brief.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-kickoff-completion-report-pack/platform-readiness-kickoff-trust-ledger.csv"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-kickoff-completion-report-pack/platform-readiness-kickoff-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-kickoff-completion-report-pack/platform-readiness-kickoff-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-kickoff-completion-report-pack/platform-readiness-kickoff-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-kickoff-completion-report-pack/platform-readiness-kickoff-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-kickoff-completion-report-pack/evidence/platform-readiness-kickoff-execution-summary.json"
    ).exists()


def test_phase3_kickoff_strict_fails_without_prereq_baseline(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    (
        tmp_path
        / "docs/artifacts/release-readiness-wrap-handoff-completion-report-pack/release-readiness-wrap-handoff-completion-report-summary.json"
    ).unlink()
    assert d61.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_phase3_kickoff_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = cli.main(
        [
            "platform-readiness-kickoff-completion-report",
            "--root",
            str(tmp_path),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    alias_rc = cli.main(
        [
            "platform-readiness-kickoff-completion-report",
            "--root",
            str(tmp_path),
            "--format",
            "text",
        ]
    )
    assert alias_rc == 0
    assert "Phase3 Kickoff Closeout summary" in capsys.readouterr().out
