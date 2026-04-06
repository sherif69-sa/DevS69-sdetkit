from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import contributor_activation_closeout_55 as d55


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-contributor-activation-closeout.md\ncontributor-activation-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-55-big-upgrade-report.md\nintegrations-contributor-activation-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        '- ** — Contributor activation #2:** escalate repeat contributors into owner tracks.\n'
        '- ** — Stabilization lane:** enforce deterministic follow-through and verification.\n',
        encoding="utf-8",
    )
    (root / "docs/integrations-contributor-activation-closeout.md").write_text(
        d55._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-55-big-upgrade-report.md").write_text(
        '#  report\n', encoding="utf-8"
    )

    summary = root / "docs/artifacts/docs-loop-closeout-pack/docs-loop-closeout-summary.json"
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
    board = root / "docs/artifacts/docs-loop-closeout-pack/docs-loop-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                '#  delivery board',
                '- [ ]  docs-loop brief committed',
                '- [ ]  docs-loop plan reviewed with owner + backup',
                '- [ ]  cross-link map exported',
                '- [ ]  KPI scorecard snapshot exported',
                '- [ ]  contributor activation priorities drafted from  learnings',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane55_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d55.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "contributor-activation-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane55_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d55.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/contributor-activation-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/contributor-activation-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/contributor-activation-closeout-pack/contributor-activation-closeout-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/contributor-activation-closeout-pack/contributor-activation-closeout-summary.md"
    ).exists()
    assert (
        tmp_path / "artifacts/contributor-activation-closeout-pack/contributor-activation-brief.md"
    ).exists()
    assert (
        tmp_path / "artifacts/contributor-activation-closeout-pack/contributor-ladder.csv"
    ).exists()
    assert (
        tmp_path
        / "artifacts/contributor-activation-closeout-pack/contributor-activation-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/contributor-activation-closeout-pack/contributor-activation-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/contributor-activation-closeout-pack/contributor-activation-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/contributor-activation-closeout-pack/contributor-activation-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/contributor-activation-closeout-pack/evidence/contributor-activation-execution-summary.json"
    ).exists()


def test_lane55_strict_fails_without_prereq_baseline(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/docs-loop-closeout-pack/docs-loop-closeout-summary.json").unlink()
    assert d55.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane55_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["contributor-activation-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Contributor Activation Closeout summary" in capsys.readouterr().out
