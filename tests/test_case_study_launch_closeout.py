from __future__ import annotations

import json
from pathlib import Path

from sdetkit import case_study_launch_closeout_73 as d73
from sdetkit import cli


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-case-study-launch-closeout.md\ncase-study-launch-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-73-big-upgrade-report.md\nintegrations-case-study-launch-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        '- ** — Case-study launch:** lock publication-quality evidence and publication readiness handoff.\n'
        '- ** — Distribution scaling:** convert  learnings into scaled distribution operations.\n',
        encoding="utf-8",
    )
    (root / "docs/integrations-case-study-launch-closeout.md").write_text(
        d73._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-73-big-upgrade-report.md").write_text(
        '#  report\n', encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/case-study-prep4-closeout-pack/case-study-prep4-closeout-summary.json"
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
        root / "docs/artifacts/case-study-prep4-closeout-pack/case-study-prep4-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                '#  delivery board',
                '- [ ]  integration brief committed',
                '- [ ]  publication-quality case-study narrative published',
                '- [ ]  controls and assumptions log exported',
                '- [ ]  KPI scorecard snapshot exported',
                '- [ ]  distribution scaling priorities drafted from  learnings',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    case_study = root / "docs/roadmap/plans/published-case-study.json"
    case_study.write_text(
        json.dumps(
            {
                "case_id": "case-study-launch-001",
                "metric": "incident-triage-mttr",
                "baseline": {"hours": 6.2},
                "after": {"hours": 3.1},
                "confidence": 0.91,
                "owner": "incident-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_lane73_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d73.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "case-study-launch-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane73_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d73.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/case-study-launch-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/case-study-launch-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/case-study-launch-closeout-pack/case-study-launch-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/case-study-launch-closeout-pack/case-study-launch-closeout-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/case-study-launch-closeout-pack/case-study-launch-integration-brief.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/case-study-launch-closeout-pack/case-study-launch-case-study-narrative.md"
    ).exists()
    assert (
        tmp_path / "artifacts/case-study-launch-closeout-pack/case-study-launch-controls-log.json"
    ).exists()
    assert (
        tmp_path / "artifacts/case-study-launch-closeout-pack/case-study-launch-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path / "artifacts/case-study-launch-closeout-pack/case-study-launch-execution-log.md"
    ).exists()
    assert (
        tmp_path / "artifacts/case-study-launch-closeout-pack/case-study-launch-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/case-study-launch-closeout-pack/case-study-launch-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/case-study-launch-closeout-pack/evidence/case-study-launch-execution-summary.json"
    ).exists()


def test_lane73_strict_fails_without_prior_closeout(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/case-study-prep4-closeout-pack/case-study-prep4-closeout-summary.json"
    ).unlink()
    assert d73.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane73_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["case-study-launch-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Case Study Launch Closeout summary" in capsys.readouterr().out
