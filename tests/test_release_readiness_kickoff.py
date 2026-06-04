from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import release_readiness_kickoff as d31


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-release-readiness-kickoff.md\nrelease-readiness-kickoff\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-31-ultra-upgrade-report.md\nintegrations-release-readiness-kickoff.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Release readiness kickoff:** set baseline metrics from end of baseline and define weekly growth targets.\n"
        "- ** — Release cadence setup:** lock weekly release rhythm and changelog publication checklist.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-release-readiness-kickoff.md").write_text(
        d31._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-31-ultra-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = root / "docs/artifacts/baseline-wrap-pack/baseline-wrap-summary.json"
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
    backlog = root / "docs/artifacts/baseline-wrap-pack/baseline-wrap-release-readiness-backlog.md"
    backlog.write_text(
        "\n".join(
            [
                "# Locked release readiness backlog",
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


def test_kickoff_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d31.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "release-readiness-kickoff"
    assert out["summary"]["activation_score"] >= 95


def test_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d31.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/release-readiness-kickoff-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/release-readiness-kickoff-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/release-readiness-kickoff-pack/release-readiness-kickoff-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/release-readiness-kickoff-pack/release-readiness-kickoff-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-kickoff-pack/release-readiness-kickoff-baseline-snapshot.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-kickoff-pack/release-readiness-kickoff-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-kickoff-pack/release-readiness-kickoff-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-kickoff-pack/evidence/release-readiness-kickoff-execution-summary.json"
    ).exists()


def test_strict_fails_when_workflow_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/baseline-wrap-pack/baseline-wrap-summary.json").unlink()
    rc = d31.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_strict_fails_when_backlog_is_not_release_readiness_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path / "docs/artifacts/baseline-wrap-pack/baseline-wrap-release-readiness-backlog.md"
    ).write_text("- [ ]  baseline\n", encoding="utf-8")
    rc = d31.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["release readiness-kickoff", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert " release readiness kickoff summary" in capsys.readouterr().out
