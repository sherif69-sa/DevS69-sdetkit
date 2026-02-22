from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day29_phase1_hardening as d29


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day29-phase1-hardening.md\nday29-phase1-hardening\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-29-ultra-upgrade-report.md\nintegrations-day29-phase1-hardening.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 29 — Phase-1 hardening:** close stale docs gaps and polish top entry pages.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day28-weekly-review.md").write_text(
        "# Weekly review #4 (Day 28)\n", encoding="utf-8"
    )
    (root / "docs/integrations-day29-phase1-hardening.md").write_text(
        d29._DAY29_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-29-ultra-upgrade-report.md").write_text("# Day 29 report\n", encoding="utf-8")


def test_day29_hardening_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d29.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day29-phase1-hardening"
    assert out["summary"]["activation_score"] >= 90


def test_day29_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d29.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day29-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day29-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day29-pack/day29-phase1-hardening-summary.json").exists()
    assert (tmp_path / "artifacts/day29-pack/day29-phase1-hardening-summary.md").exists()
    assert (tmp_path / "artifacts/day29-pack/day29-stale-gaps.json").exists()
    assert (tmp_path / "artifacts/day29-pack/day29-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day29-pack/evidence/day29-execution-summary.json").exists()


def test_day29_strict_fails_when_sections_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/integrations-day29-phase1-hardening.md").write_text(
        "# Day 29 — Phase-1 hardening\n", encoding="utf-8"
    )
    rc = d29.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day29_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day29-phase1-hardening", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 29 phase-1 hardening summary" in capsys.readouterr().out
