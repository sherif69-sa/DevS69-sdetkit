from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import phase2_wrap_handoff_closeout_60 as d60


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-phase2-wrap-handoff-closeout.md\nphase2-wrap-handoff-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-60-big-upgrade-report.md\nintegrations-phase2-wrap-handoff-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Phase-2 wrap + handoff:** publish full Phase-2 report and lock Phase-3 execution board.\n"
        "- ** — Phase-3 kickoff:** set Phase-3 baseline and define ecosystem/trust KPIs.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-phase2-wrap-handoff-closeout.md").write_text(
        d60._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-60-big-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = (
        root / "docs/artifacts/phase3-preplan-closeout-pack/phase3-preplan-closeout-summary.json"
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
    board = root / "docs/artifacts/phase3-preplan-closeout-pack/phase3-preplan-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  Phase-3 pre-plan brief committed",
                "- [ ]  pre-plan reviewed with owner + backup",
                "- [ ]  risk ledger exported",
                "- [ ]  KPI scorecard snapshot exported",
                "- [ ]  execution priorities drafted from  learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane60_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d60.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "phase2-wrap-handoff-closeout"
    assert out["summary"]["activation_score"] >= 95
    assert "## Required inputs ()" not in d60._DEFAULT_PAGE_TEMPLATE
    assert "The  lane references" not in d60._DEFAULT_PAGE_TEMPLATE
    assert "## Why  matters" not in d60._DEFAULT_PAGE_TEMPLATE


def test_lane60_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d60.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/phase2-wrap-handoff-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/phase2-wrap-handoff-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-closeout-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-closeout-summary.md"
    ).exists()
    assert (
        tmp_path / "artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-brief.md"
    ).exists()
    assert (
        tmp_path / "artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-risk-ledger.csv"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase2-wrap-handoff-closeout-pack/evidence/phase2-wrap-handoff-execution-summary.json"
    ).exists()


def test_lane60_strict_fails_without_phase3_preplan(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/phase3-preplan-closeout-pack/phase3-preplan-closeout-summary.json"
    ).unlink()
    assert d60.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane60_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["phase2-wrap-handoff-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Phase 2 Wrap Handoff Closeout summary" in capsys.readouterr().out


def test_lane60_docs_page_has_no_lane_lane_typo() -> None:
    docs_page = (
        Path(__file__).resolve().parents[1] / "docs/integrations-phase2-wrap-handoff-closeout.md"
    )
    page_text = docs_page.read_text(encoding="utf-8")
    assert "Lane lane" not in page_text
