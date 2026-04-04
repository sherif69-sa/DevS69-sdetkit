from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import execution_prioritization_closeout_50 as d50


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-execution-prioritization-closeout.md\nexecution-prioritization-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-50-big-upgrade-report.md\nintegrations-execution-prioritization-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 50 — Execution prioritization lock:** convert weekly-review wins into a deterministic execution board.\n"
        "- **Day 51 — Case snippet #1:** publish mini-case on reliability or quality gate value.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-execution-prioritization-closeout.md").write_text(
        d50._DAY50_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/impact-50-big-upgrade-report.md").write_text(
        "# Day 50 report\n", encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/weekly-review-closeout-pack-49/weekly-review-closeout-summary-49.json"
    )
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
    board = root / "docs/artifacts/weekly-review-closeout-pack-49/delivery-board-49.md"
    board.write_text(
        "\n".join(
            [
                "# Day 49 delivery board",
                "- [ ] Day 49 weekly review brief committed",
                "- [ ] Day 49 priorities reviewed with owner + backup",
                "- [ ] Day 49 risk register exported",
                "- [ ] Day 49 KPI scorecard snapshot exported",
                "- [ ] Day 50 execution priorities drafted from Day 49 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane50_execution_prioritization_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d50.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "execution-prioritization-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane50_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d50.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/execution-prioritization-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/execution-prioritization-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/execution-prioritization-pack/execution-prioritization-closeout-summary.json"
    ).exists()
    assert (tmp_path / "artifacts/execution-prioritization-pack/execution-prioritization-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/execution-prioritization-pack/execution-prioritization-brief.md").exists()
    assert (tmp_path / "artifacts/execution-prioritization-pack/execution-prioritization-risk-register.csv").exists()
    assert (tmp_path / "artifacts/execution-prioritization-pack/execution-prioritization-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/execution-prioritization-pack/execution-prioritization-execution-log.md").exists()
    assert (tmp_path / "artifacts/execution-prioritization-pack/execution-prioritization-delivery-board.md").exists()
    assert (
        tmp_path / "artifacts/execution-prioritization-pack/execution-prioritization-validation-commands.md"
    ).exists()
    assert (
        tmp_path / "artifacts/execution-prioritization-pack/evidence/execution-prioritization-execution-summary.json"
    ).exists()


def test_lane50_strict_fails_when_lane49_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/weekly-review-closeout-pack-49/weekly-review-closeout-summary-49.json"
    ).unlink()
    rc = d50.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_lane50_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["execution-prioritization-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 50 execution prioritization closeout summary" in capsys.readouterr().out
