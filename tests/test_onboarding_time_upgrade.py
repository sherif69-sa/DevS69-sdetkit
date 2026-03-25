from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import onboarding_time_upgrade as otu


def _write_fixture(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-24-ultra-upgrade-report.md\n"
        "docs/onboarding-optimization.md\n"
        "Onboarding optimization\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "Onboarding optimization\ndocs/onboarding-optimization.md\nonboarding-optimization\n",
        encoding="utf-8",
    )
    (root / "docs/onboarding-optimization.md").write_text(otu._DAY24_DEFAULT_PAGE, encoding="utf-8")
    (root / "src/sdetkit").mkdir(parents=True, exist_ok=True)
    (root / "src/sdetkit/onboarding.py").write_text(
        "--role\n--platform\npython -m sdetkit doctor --format text\n", encoding="utf-8"
    )


def test_onboarding_json(tmp_path: Path, capsys) -> None:
    _write_fixture(tmp_path)

    rc = otu.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0

    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "onboarding-optimization"
    assert out["summary"]["onboarding_score"] == 100.0


def test_onboarding_emit_pack_and_execute(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    rc = otu.main(
        [
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--strict",
            "--emit-pack-dir",
            "artifacts/onboarding-optimization-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/onboarding-optimization-pack/evidence",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/onboarding-optimization-pack/onboarding-optimization-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/onboarding-optimization-pack/onboarding-optimization-scorecard.md"
    ).exists()
    assert (
        tmp_path / "artifacts/onboarding-optimization-pack/onboarding-optimization-checklist.md"
    ).exists()
    assert (
        tmp_path / "artifacts/onboarding-optimization-pack/onboarding-optimization-runbook.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/onboarding-optimization-pack/onboarding-optimization-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/onboarding-optimization-pack/evidence/onboarding-optimization-execution-summary.json"
    ).exists()


def test_onboarding_strict_fails_when_sections_missing(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    (tmp_path / "docs/onboarding-optimization.md").write_text(
        "# Onboarding optimization\n", encoding="utf-8"
    )

    rc = otu.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 1


def test_cli_dispatch(tmp_path: Path, capsys) -> None:
    _write_fixture(tmp_path)

    rc = cli.main(["onboarding-optimization", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Onboarding optimization" in capsys.readouterr().out
