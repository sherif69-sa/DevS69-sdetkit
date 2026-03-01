from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day57_kpi_deep_audit_closeout as d57


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day57-kpi-deep-audit-closeout.md\nday57-kpi-deep-audit-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-57-big-upgrade-report.md\nintegrations-day57-kpi-deep-audit-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 57 — KPI deep audit:** validate strict trendlines and blockers.\n"
        "- **Day 58 — Execution sprint:** convert audit outcomes into shipped changes.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day57-kpi-deep-audit-closeout.md").write_text(
        d57._DAY57_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-57-big-upgrade-report.md").write_text("# Day 57 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day56-stabilization-closeout-pack/day56-stabilization-closeout-summary.json"
    )
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
    board = root / "docs/artifacts/day56-stabilization-closeout-pack/day56-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 56 delivery board",
                "- [ ] Day 56 stabilization brief committed",
                "- [ ] Day 56 stabilization plan reviewed with owner + backup",
                "- [ ] Day 56 risk ledger exported",
                "- [ ] Day 56 KPI scorecard snapshot exported",
                "- [ ] Day 57 deep-audit priorities drafted from Day 56 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day57_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d57.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day57-kpi-deep-audit-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day57_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d57.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day57-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day57-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day57-pack/day57-kpi-deep-audit-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day57-pack/day57-kpi-deep-audit-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day57-pack/day57-kpi-deep-audit-brief.md").exists()
    assert (tmp_path / "artifacts/day57-pack/day57-risk-ledger.csv").exists()
    assert (tmp_path / "artifacts/day57-pack/day57-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day57-pack/day57-execution-log.md").exists()
    assert (tmp_path / "artifacts/day57-pack/day57-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day57-pack/day57-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day57-pack/evidence/day57-execution-summary.json").exists()


def test_day57_strict_fails_without_day56(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day56-stabilization-closeout-pack/day56-stabilization-closeout-summary.json"
    ).unlink()
    assert d57.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day57_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day57-kpi-deep-audit-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 57 KPI deep-audit closeout summary" in capsys.readouterr().out
