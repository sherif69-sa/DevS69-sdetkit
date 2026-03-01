from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day47_reliability_closeout as d47


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day47-reliability-closeout.md\nday47-reliability-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-47-big-upgrade-report.md\nintegrations-day47-reliability-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 46 — Optimization lane continuation:** convert Day 45 expansion wins into optimization plays.\n"
        "- **Day 47 — Reliability lane continuation:** convert Day 46 optimization wins into reliability plays.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day47-reliability-closeout.md").write_text(
        d47._DAY47_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-47-big-upgrade-report.md").write_text("# Day 47 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day46-optimization-closeout-pack/day46-optimization-closeout-summary.json"
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
    board = root / "docs/artifacts/day46-optimization-closeout-pack/day46-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 46 delivery board",
                "- [ ] Day 46 optimization plan draft committed",
                "- [ ] Day 46 review notes captured with owner + backup",
                "- [ ] Day 46 bottleneck map exported",
                "- [ ] Day 46 KPI scorecard snapshot exported",
                "- [ ] Day 47 reliability priorities drafted from Day 46 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day47_reliability_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d47.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day47-reliability-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day47_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d47.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day47-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day47-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day47-pack/day47-reliability-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day47-pack/day47-reliability-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day47-pack/day47-reliability-plan.md").exists()
    assert (tmp_path / "artifacts/day47-pack/day47-incident-map.csv").exists()
    assert (tmp_path / "artifacts/day47-pack/day47-reliability-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day47-pack/day47-execution-log.md").exists()
    assert (tmp_path / "artifacts/day47-pack/day47-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day47-pack/day47-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day47-pack/evidence/day47-execution-summary.json").exists()


def test_day47_strict_fails_when_day46_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day46-optimization-closeout-pack/day46-optimization-closeout-summary.json"
    ).unlink()
    rc = d47.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day47_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day47-reliability-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 47 reliability closeout summary" in capsys.readouterr().out
