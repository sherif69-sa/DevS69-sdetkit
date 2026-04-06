from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import phase2_kickoff_31 as d31


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-phase2-kickoff.md\nphase2-kickoff\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-31-ultra-upgrade-report.md\nintegrations-phase2-kickoff.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Phase-2 kickoff:** set baseline metrics from end of Phase 1 and define weekly growth targets.\n"
        "- ** — Release cadence setup:** lock weekly release rhythm and changelog publication checklist.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-phase2-kickoff.md").write_text(
        d31._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-31-ultra-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = root / "docs/artifacts/phase1-wrap-pack/phase1-wrap-summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 97, "strict_pass": True},
                "rollup": {"average_activation_score": 96.0},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    backlog = root / "docs/artifacts/phase1-wrap-pack/phase1-wrap-phase2-backlog.md"
    backlog.write_text(
        "\n".join(
            [
                "# Locked Phase-2 backlog",
                "- [ ]  baseline metrics + weekly targets",
                "- [ ]  release cadence + changelog checklist",
                "- [ ]  demo asset #1 (doctor)",
                "- [ ]  demo asset #2 (repo audit)",
                "- [ ]  weekly review #5",
                "- [ ]  demo asset #3 (security gate)",
                "- [ ]  demo asset #4 (cassette replay)",
                "- [ ]  distribution batch #1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane31_kickoff_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d31.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "phase2-kickoff"
    assert out["summary"]["activation_score"] >= 95


def test_lane31_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d31.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/phase2-kickoff-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/phase2-kickoff-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/phase2-kickoff-pack/phase2-kickoff-summary.json").exists()
    assert (tmp_path / "artifacts/phase2-kickoff-pack/phase2-kickoff-summary.md").exists()
    assert (
        tmp_path / "artifacts/phase2-kickoff-pack/phase2-kickoff-baseline-snapshot.json"
    ).exists()
    assert (tmp_path / "artifacts/phase2-kickoff-pack/phase2-kickoff-delivery-board.md").exists()
    assert (
        tmp_path / "artifacts/phase2-kickoff-pack/phase2-kickoff-validation-commands.md"
    ).exists()
    assert (
        tmp_path / "artifacts/phase2-kickoff-pack/evidence/phase2-kickoff-execution-summary.json"
    ).exists()


def test_lane31_strict_fails_when_lane30_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/phase1-wrap-pack/phase1-wrap-summary.json").unlink()
    rc = d31.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_lane31_strict_fails_when_backlog_is_not_phase2_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/phase1-wrap-pack/phase1-wrap-phase2-backlog.md").write_text(
        "- [ ]  baseline\n", encoding="utf-8"
    )
    rc = d31.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_lane31_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["phase2-kickoff", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert " phase-2 kickoff summary" in capsys.readouterr().out
