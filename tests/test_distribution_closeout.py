from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import distribution_closeout_36 as d36


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-distribution-closeout.md\ndistribution-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-36-big-upgrade-report.md\nintegrations-distribution-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        '- ** — Distribution closeout:** publish channel-ready  KPI narrative with owners and posting windows.\n'
        '- ** — Experiment lane:** convert  misses into controlled growth experiments.\n',
        encoding="utf-8",
    )
    (root / "docs/integrations-distribution-closeout.md").write_text(
        d36._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-36-big-upgrade-report.md").write_text(
        '#  report\n', encoding="utf-8"
    )

    summary = root / "docs/artifacts/kpi-instrumentation-pack/kpi-instrumentation-summary.json"
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
    board = root / "docs/artifacts/kpi-instrumentation-pack/delivery-board.md"
    board.write_text(
        "\n".join(
            [
                '#  delivery board',
                '- [ ]  KPI dictionary committed',
                '- [ ]  dashboard snapshot exported',
                '- [ ]  alert policy reviewed with owner + backup',
                '- [ ]  distribution message references KPI shifts',
                '- [ ]  experiment backlog seeded from KPI misses',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane36_distribution_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d36.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "distribution-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane36_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d36.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/distribution-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/distribution-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/distribution-closeout-pack/distribution-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/distribution-closeout-pack/distribution-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/distribution-closeout-pack/distribution-message-kit.md").exists()
    assert (tmp_path / "artifacts/distribution-closeout-pack/launch-plan.csv").exists()
    assert (tmp_path / "artifacts/distribution-closeout-pack/experiment-backlog.md").exists()
    assert (tmp_path / "artifacts/distribution-closeout-pack/delivery-board.md").exists()
    assert (tmp_path / "artifacts/distribution-closeout-pack/validation-commands.md").exists()
    assert (
        tmp_path / "artifacts/distribution-closeout-pack/evidence/execution-summary.json"
    ).exists()


def test_lane36_strict_fails_when_lane35_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/kpi-instrumentation-pack/kpi-instrumentation-summary.json").unlink()
    rc = d36.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_lane36_strict_fails_when_lane35_board_is_not_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/kpi-instrumentation-pack/delivery-board.md").write_text(
        '- [ ]  distribution message references KPI shifts\n', encoding="utf-8"
    )
    rc = d36.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_lane36_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["distribution-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert ' community distribution summary' in capsys.readouterr().out
