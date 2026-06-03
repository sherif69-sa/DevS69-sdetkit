from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import platform_readiness_preplan as d59
from tests.workflow_fixture_seed import seed_contract_anchors


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-platform-readiness-preplan-workflow.md\nplatform-readiness-preplan-completion-report\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-59-big-upgrade-report.md\nintegrations-platform-readiness-preplan-workflow.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — platform readiness preplan:** convert Release readiness learnings into Platform readiness priorities.\n"
        "- ** — release readiness wrap handoff:** publish full Release readiness report and lock Platform readiness execution board.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-platform-readiness-preplan-workflow.md").write_text(
        d59._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-59-big-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/release-readiness-hardening-completion-report-pack/release-readiness-hardening-completion-report-summary.json"
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
        / "docs/artifacts/release-readiness-hardening-completion-report-pack/release-readiness-hardening-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  release readiness hardening brief committed",
                "- [ ]  hardening plan reviewed with owner + backup",
                "- [ ]  risk ledger exported",
                "- [ ]  KPI scorecard snapshot exported",
                "- [ ]  pre-plan priorities drafted from  learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_phase3_preplan_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d59.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "platform-readiness-preplan-completion-report"
    assert out["summary"]["activation_score"] >= 95


def test_phase3_preplan_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d59.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/platform-readiness-preplan-completion-report-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/platform-readiness-preplan-completion-report-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-completion-report-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-completion-report-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-brief.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-risk-ledger.csv"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/platform-readiness-preplan-completion-report-pack/evidence/platform-readiness-preplan-execution-summary.json"
    ).exists()


def test_phase3_preplan_strict_fails_without_phase2_hardening(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    (
        tmp_path
        / "docs/artifacts/release-readiness-hardening-completion-report-pack/release-readiness-hardening-completion-report-summary.json"
    ).unlink()
    assert d59.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_phase3_preplan_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = cli.main(
        [
            "platform-readiness-preplan-completion-report",
            "--root",
            str(tmp_path),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    assert "Phase3 Preplan Closeout summary" in capsys.readouterr().out
