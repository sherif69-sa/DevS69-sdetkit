from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import onboarding_time_upgrade as otu


def _write_fixture(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text("day-24-ultra-upgrade-report.md\n", encoding="utf-8")
    (root / "README.md").write_text(
        "docs/integrations-onboarding-time-upgrade.md\nonboarding-time-upgrade\n", encoding="utf-8"
    )
    (root / "docs/integrations-onboarding-time-upgrade.md").write_text(
        otu._DAY24_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "src/sdetkit").mkdir(parents=True, exist_ok=True)
    (root / "src/sdetkit/onboarding.py").write_text(
        "--role\n--platform\npython -m sdetkit doctor --format text\n", encoding="utf-8"
    )


def test_day24_onboarding_json(tmp_path: Path, capsys) -> None:
    _write_fixture(tmp_path)

    rc = otu.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0

    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day24-onboarding-time-upgrade"
    assert out["summary"]["onboarding_score"] == 100.0


def test_day24_onboarding_emit_pack_and_execute(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    rc = otu.main(
        [
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--strict",
            "--emit-pack-dir",
            "artifacts/day24-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day24-pack/evidence",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day24-pack/day24-onboarding-summary.json").exists()
    assert (tmp_path / "artifacts/day24-pack/day24-onboarding-scorecard.md").exists()
    assert (tmp_path / "artifacts/day24-pack/day24-onboarding-checklist.md").exists()
    assert (tmp_path / "artifacts/day24-pack/day24-time-to-first-success-runbook.md").exists()
    assert (tmp_path / "artifacts/day24-pack/day24-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day24-pack/evidence/day24-execution-summary.json").exists()


def test_day24_onboarding_strict_fails_when_sections_missing(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    (tmp_path / "docs/integrations-onboarding-time-upgrade.md").write_text(
        "# Onboarding time upgrade (Day 24)\n", encoding="utf-8"
    )

    rc = otu.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 1


def test_day24_cli_dispatch(tmp_path: Path, capsys) -> None:
    _write_fixture(tmp_path)

    rc = cli.main(["onboarding-time-upgrade", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 24 onboarding time upgrade" in capsys.readouterr().out
