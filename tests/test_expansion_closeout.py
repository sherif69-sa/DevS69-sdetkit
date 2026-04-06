from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import expansion_closeout_45 as d45


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-expansion-closeout.md\nexpansion-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-45-big-upgrade-report.md\nintegrations-expansion-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        '- ** — Expansion closeout lane:** convert  scale proof into deterministic expansion loops.\n'
        '- ** — Optimization lane continuation:** convert  expansion wins into optimization plays.\n',
        encoding="utf-8",
    )
    (root / "docs/integrations-expansion-closeout.md").write_text(
        d45._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-45-big-upgrade-report.md").write_text(
        '#  report\n', encoding="utf-8"
    )

    summary = root / "docs/artifacts/scale-closeout-pack/scale-closeout-summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 99, "strict_pass": True},
                "checks": [{"check_id": "ok", "passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/scale-closeout-pack/scale-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                '#  delivery board',
                '- [ ]  scale plan draft committed',
                '- [ ]  review notes captured with owner + backup',
                '- [ ]  growth matrix exported',
                '- [ ]  KPI scorecard snapshot exported',
                '- [ ]  expansion priorities drafted from  learnings',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane45_expansion_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d45.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "expansion-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane45_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d45.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/expansion-closeout-pack-45",
            "--execute",
            "--evidence-dir",
            "artifacts/expansion-closeout-pack-45/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/expansion-closeout-pack-45/expansion-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/expansion-closeout-pack-45/expansion-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/expansion-closeout-pack-45/expansion-plan.md").exists()
    assert (tmp_path / "artifacts/expansion-closeout-pack-45/expansion-growth-matrix.csv").exists()
    assert (tmp_path / "artifacts/expansion-closeout-pack-45/expansion-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/expansion-closeout-pack-45/expansion-execution-log.md").exists()
    assert (tmp_path / "artifacts/expansion-closeout-pack-45/expansion-delivery-board.md").exists()
    assert (
        tmp_path / "artifacts/expansion-closeout-pack-45/expansion-validation-commands.md"
    ).exists()
    assert (
        tmp_path / "artifacts/expansion-closeout-pack-45/evidence/expansion-execution-summary.json"
    ).exists()


def test_lane45_strict_fails_when_lane44_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/scale-closeout-pack/scale-closeout-summary.json").unlink()
    rc = d45.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_lane45_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["expansion-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert ' expansion closeout summary' in capsys.readouterr().out
