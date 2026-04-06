from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import scale_closeout_44 as d44


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-scale-closeout.md\nscale-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-44-big-upgrade-report.md\nintegrations-scale-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        '- ** — Scale closeout lane:** convert  acceleration proof into deterministic scale loops.\n'
        '- ** — Expansion lane continuation:** convert  scale wins into expansion plays.\n',
        encoding="utf-8",
    )
    (root / "docs/integrations-scale-closeout.md").write_text(
        d44._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-44-big-upgrade-report.md").write_text(
        '#  report\n', encoding="utf-8"
    )

    summary = root / "docs/artifacts/acceleration-closeout-pack/acceleration-closeout-summary.json"
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
    board = root / "docs/artifacts/acceleration-closeout-pack/delivery-board.md"
    board.write_text(
        "\n".join(
            [
                '#  delivery board',
                '- [ ]  acceleration plan draft committed',
                '- [ ]  review notes captured with owner + backup',
                '- [ ]  remediation matrix exported',
                '- [ ]  KPI scorecard snapshot exported',
                '- [ ]  scale priorities drafted from  learnings',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane44_scale_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d44.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "scale-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane44_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d44.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/scale-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/scale-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/scale-closeout-pack/scale-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/scale-closeout-pack/scale-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/scale-closeout-pack/scale-plan.md").exists()
    assert (tmp_path / "artifacts/scale-closeout-pack/scale-growth-matrix.csv").exists()
    assert (tmp_path / "artifacts/scale-closeout-pack/scale-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/scale-closeout-pack/scale-execution-log.md").exists()
    assert (tmp_path / "artifacts/scale-closeout-pack/scale-delivery-board.md").exists()
    assert (tmp_path / "artifacts/scale-closeout-pack/scale-validation-commands.md").exists()
    assert (
        tmp_path / "artifacts/scale-closeout-pack/evidence/scale-execution-summary.json"
    ).exists()


def test_lane44_strict_fails_when_lane43_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path / "docs/artifacts/acceleration-closeout-pack/acceleration-closeout-summary.json"
    ).unlink()
    rc = d44.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_lane44_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["scale-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Scale closeout summary" in capsys.readouterr().out
