from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import optimization_closeout_42 as d42


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-optimization-closeout-foundation.md\noptimization-closeout-foundation\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-42-big-upgrade-report.md\nintegrations-optimization-closeout-foundation.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Optimization Closeout Foundation — Optimization closeout lane:** convert  evidence into deterministic remediation loops.\n"
        "- ** — Acceleration lane kickoff:** scale Optimization Closeout Foundation optimizations into repeatable growth plays.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-optimization-closeout-foundation.md").write_text(
        d42._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-42-big-upgrade-report.md").write_text(
        "# Optimization Closeout Foundation report\n", encoding="utf-8"
    )

    summary = root / "docs/artifacts/expansion-automation-pack/expansion-automation-summary.json"
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
    board = root / "docs/artifacts/expansion-automation-pack/delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  expansion plan draft committed",
                "- [ ]  review notes captured with owner + backup",
                "- [ ]  automation matrix exported",
                "- [ ]  KPI scorecard snapshot exported",
                "- [ ] Optimization Closeout Foundation optimization priorities drafted from  learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane42_optimization_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d42.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "optimization-closeout-foundation"
    assert out["summary"]["activation_score"] >= 95


def test_lane42_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d42.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/optimization-closeout-foundation-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/optimization-closeout-foundation-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/optimization-closeout-foundation-pack/optimization-closeout-foundation-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/optimization-closeout-foundation-pack/optimization-closeout-foundation-summary.md"
    ).exists()
    assert (
        tmp_path / "artifacts/optimization-closeout-foundation-pack/optimization-plan.md"
    ).exists()
    assert (
        tmp_path / "artifacts/optimization-closeout-foundation-pack/remediation-matrix.csv"
    ).exists()
    assert (
        tmp_path / "artifacts/optimization-closeout-foundation-pack/optimization-kpi-scorecard.json"
    ).exists()
    assert (tmp_path / "artifacts/optimization-closeout-foundation-pack/execution-log.md").exists()
    assert (tmp_path / "artifacts/optimization-closeout-foundation-pack/delivery-board.md").exists()
    assert (
        tmp_path / "artifacts/optimization-closeout-foundation-pack/validation-commands.md"
    ).exists()
    assert (
        tmp_path / "artifacts/optimization-closeout-foundation-pack/evidence/execution-summary.json"
    ).exists()


def test_lane42_strict_fails_when_lane41_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path / "docs/artifacts/expansion-automation-pack/expansion-automation-summary.json"
    ).unlink()
    rc = d42.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_lane42_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["optimization-closeout-foundation", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert (
        "Optimization Closeout Foundation optimization closeout summary" in capsys.readouterr().out
    )
