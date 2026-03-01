from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import kpi_audit as kpa


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-kpi-audit.md\nkpi-audit\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text("day-27-ultra-upgrade-report.md\n", encoding="utf-8")
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 27 — KPI audit:** compare baseline vs current (stars/week, CTR, discussions, PRs).\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-kpi-audit.md").write_text(kpa._DAY27_DEFAULT_PAGE, encoding="utf-8")
    pack = root / "docs/artifacts/day27-kpi-pack"
    pack.mkdir(parents=True, exist_ok=True)
    (pack / "day27-kpi-baseline.json").write_text(
        json.dumps(kpa._DEFAULT_BASELINE) + "\n", encoding="utf-8"
    )
    (pack / "day27-kpi-current.json").write_text(
        json.dumps(kpa._DEFAULT_CURRENT) + "\n", encoding="utf-8"
    )


def test_day27_kpi_audit_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = kpa.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day27-kpi-audit"
    assert out["summary"]["activation_score"] >= 90


def test_day27_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = kpa.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day27-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day27-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day27-pack/day27-kpi-summary.json").exists()
    assert (tmp_path / "artifacts/day27-pack/day27-kpi-scorecard.md").exists()
    assert (tmp_path / "artifacts/day27-pack/day27-kpi-delta-table.md").exists()
    assert (tmp_path / "artifacts/day27-pack/day27-kpi-corrective-actions.md").exists()
    assert (tmp_path / "artifacts/day27-pack/day27-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day27-pack/evidence/day27-execution-summary.json").exists()


def test_day27_strict_fails_when_sections_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/integrations-kpi-audit.md").write_text(
        "# KPI audit (Day 27)\n", encoding="utf-8"
    )
    rc = kpa.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day27_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["kpi-audit", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 27 KPI audit summary" in capsys.readouterr().out
