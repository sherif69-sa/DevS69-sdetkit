from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import phase3_kickoff_closeout_61 as d61


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-phase3-kickoff-closeout.md\nphase3-kickoff-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-61-big-upgrade-report.md\nintegrations-phase3-kickoff-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        '- ** — Phase-3 kickoff:** set Phase-3 baseline and define ecosystem/trust KPIs.\n'
        '- ** — Community program setup:** publish office-hours cadence and participation rules.\n',
        encoding="utf-8",
    )
    (root / "docs/integrations-phase3-kickoff-closeout.md").write_text(
        d61._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-61-big-upgrade-report.md").write_text(
        '#  report\n', encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-closeout-summary.json"
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
        / "docs/artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                '#  delivery board',
                '- [ ]  Phase-2 wrap + handoff brief committed',
                '- [ ]  wrap reviewed with owner + backup',
                '- [ ]  risk ledger exported',
                '- [ ]  KPI scorecard snapshot exported',
                '- [ ]  execution priorities drafted from  learnings',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane61_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d61.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "phase3-kickoff-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane61_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d61.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/phase3-kickoff-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/phase3-kickoff-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-brief.md").exists()
    assert (
        tmp_path / "artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-trust-ledger.csv"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-execution-log.md"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-delivery-board.md"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase3-kickoff-closeout-pack/evidence/phase3-kickoff-execution-summary.json"
    ).exists()


def test_lane61_strict_fails_without_prereq_baseline(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/phase2-wrap-handoff-closeout-pack/phase2-wrap-handoff-closeout-summary.json"
    ).unlink()
    assert d61.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane61_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["phase3-kickoff-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    alias_rc = cli.main(["phase3-kickoff-closeout", "--root", str(tmp_path), "--format", "text"])
    assert alias_rc == 0
    assert "Phase3 Kickoff Closeout summary" in capsys.readouterr().out
