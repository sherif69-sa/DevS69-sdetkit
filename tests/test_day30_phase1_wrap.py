from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day30_phase1_wrap as d30


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day30-phase1-wrap.md\nday30-phase1-wrap\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-30-ultra-upgrade-report.md\nintegrations-day30-phase1-wrap.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 30 — Phase-1 wrap + handoff:** publish a full report and lock Phase-2 backlog.\n"
        "- **Day 31 — Phase-2 kickoff:** set baseline metrics from end of Phase 1 and define weekly growth targets.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day30-phase1-wrap.md").write_text(
        d30._DAY30_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-30-ultra-upgrade-report.md").write_text("# Day 30 report\n", encoding="utf-8")

    for rel in [
        "docs/artifacts/day27-kpi-pack/day27-kpi-summary.json",
        "docs/artifacts/day28-weekly-pack/day28-weekly-review-summary.json",
        "docs/artifacts/day29-hardening-pack/day29-phase1-hardening-summary.json",
    ]:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"summary": {"activation_score": 93}}, indent=2), encoding="utf-8")


def test_day30_wrap_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d30.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day30-phase1-wrap"
    assert out["summary"]["activation_score"] >= 90


def test_day30_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d30.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day30-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day30-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day30-pack/day30-phase1-wrap-summary.json").exists()
    assert (tmp_path / "artifacts/day30-pack/day30-phase1-wrap-summary.md").exists()
    assert (tmp_path / "artifacts/day30-pack/day30-phase2-backlog.md").exists()
    assert (tmp_path / "artifacts/day30-pack/day30-handoff-actions.md").exists()
    assert (tmp_path / "artifacts/day30-pack/day30-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day30-pack/evidence/day30-execution-summary.json").exists()


def test_day30_strict_fails_when_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day29-hardening-pack/day29-phase1-hardening-summary.json").unlink()
    rc = d30.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day30_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day30-phase1-wrap", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 30 phase-1 wrap summary" in capsys.readouterr().out
