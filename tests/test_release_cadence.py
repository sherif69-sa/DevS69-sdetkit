from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import release_cadence_32 as d32


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-release-cadence.md\nrelease-cadence\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-32-ultra-upgrade-report.md\nintegrations-release-cadence.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Release cadence setup:** lock weekly release rhythm and changelog publication checklist.\n"
        "- ** — Demo asset #1:** produce/publish `doctor` workflow short video or GIF.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-release-cadence.md").write_text(
        d32._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-32-ultra-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = root / "docs/artifacts/phase2-kickoff-pack/phase2-kickoff-summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 98, "strict_pass": True},
                "checks": [{"check_id": "ok", "passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/phase2-kickoff-pack/phase2-kickoff-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  baseline metrics snapshot emitted",
                "- [ ]  release cadence checklist drafted",
                "- [ ]  demo asset plan (doctor) assigned",
                "- [ ]  demo asset plan (repo audit) assigned",
                "- [ ]  weekly review preparation checklist ready",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_release_cadence_release_cadence_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d32.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "release-cadence"
    assert out["summary"]["activation_score"] >= 95


def test_release_cadence_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d32.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/release-cadence-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/release-cadence-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/release-cadence-pack/release-cadence-summary.json").exists()
    assert (tmp_path / "artifacts/release-cadence-pack/release-cadence-summary.md").exists()
    assert (tmp_path / "artifacts/release-cadence-pack/release-cadence-calendar.json").exists()
    assert (tmp_path / "artifacts/release-cadence-pack/release-changelog-template.md").exists()
    assert (tmp_path / "artifacts/release-cadence-pack/release-delivery-board.md").exists()
    assert (tmp_path / "artifacts/release-cadence-pack/release-validation-commands.md").exists()
    assert (
        tmp_path / "artifacts/release-cadence-pack/evidence/release-cadence-execution-summary.json"
    ).exists()


def test_release_cadence_strict_fails_when_lane31_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/phase2-kickoff-pack/phase2-kickoff-summary.json").unlink()
    rc = d32.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_release_cadence_strict_fails_when_lane31_board_is_not_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/phase2-kickoff-pack/phase2-kickoff-delivery-board.md").write_text(
        "- [ ]  release cadence checklist drafted\n", encoding="utf-8"
    )
    rc = d32.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_release_cadence_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["release-cadence", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert " release cadence summary" in capsys.readouterr().out
