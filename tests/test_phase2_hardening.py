from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import release_readiness_hardening as d58
from tests.workflow_fixture_seed import seed_contract_anchors


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-release-readiness-hardening-workflow.md\nrelease-readiness-hardening-completion-report\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-58-big-upgrade-report.md\nintegrations-release-readiness-hardening-workflow.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — release readiness hardening:** polish highest-traffic pages and remove top friction points.\n"
        "- ** — platform readiness preplan:** convert Release readiness learnings into Platform readiness priorities.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-release-readiness-hardening-workflow.md").write_text(
        d58._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-58-big-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = (
        root / "docs/artifacts/kpi-deep-audit-closeout-pack/kpi-deep-audit-closeout-summary.json"
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
    board = root / "docs/artifacts/kpi-deep-audit-closeout-pack/kpi-deep-audit-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  KPI deep audit brief committed",
                "- [ ]  deep-audit plan reviewed with owner + backup",
                "- [ ]  risk ledger exported",
                "- [ ]  KPI scorecard snapshot exported",
                "- [ ]  execution priorities drafted from  learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_phase2_hardening_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d58.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "release-readiness-hardening-completion-report"
    assert out["summary"]["activation_score"] >= 95


def test_phase2_hardening_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d58.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/release-readiness-hardening-completion-report-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/release-readiness-hardening-completion-report-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/release-readiness-hardening-completion-report-pack/release-readiness-hardening-completion-report-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-hardening-completion-report-pack/release-readiness-hardening-completion-report-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-hardening-completion-report-pack/release-readiness-hardening-brief.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-hardening-completion-report-pack/release-readiness-hardening-risk-ledger.csv"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-hardening-completion-report-pack/release-readiness-hardening-scorecard.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-hardening-completion-report-pack/release-readiness-hardening-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-hardening-completion-report-pack/release-readiness-hardening-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-hardening-completion-report-pack/release-readiness-hardening-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-hardening-completion-report-pack/evidence/release-readiness-hardening-execution-summary.json"
    ).exists()


def test_phase2_hardening_strict_fails_without_kpi_deep_audit(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    (
        tmp_path
        / "docs/artifacts/kpi-deep-audit-closeout-pack/kpi-deep-audit-closeout-summary.json"
    ).unlink()
    assert d58.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_phase2_hardening_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = cli.main(
        [
            "release-readiness-hardening-completion-report",
            "--root",
            str(tmp_path),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    assert "Phase 2 Hardening Closeout summary" in capsys.readouterr().out
