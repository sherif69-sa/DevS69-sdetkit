from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import faq_objections as fqo


def _write_fixture(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text("day-23-ultra-upgrade-report.md\n", encoding="utf-8")
    (root / "README.md").write_text(
        "docs/integrations-faq-objections.md\nrelease-narrative\n", encoding="utf-8"
    )
    (root / "docs/integrations-faq-objections.md").write_text(
        fqo._DAY23_DEFAULT_PAGE, encoding="utf-8"
    )


def test_day23_faq_json(tmp_path: Path, capsys) -> None:
    _write_fixture(tmp_path)

    rc = fqo.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0

    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day23-faq-objections"
    assert out["summary"]["faq_score"] == 100.0


def test_day23_faq_emit_pack_and_execute(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    rc = fqo.main(
        [
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--strict",
            "--emit-pack-dir",
            "artifacts/day23-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day23-pack/evidence",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day23-pack/day23-faq-summary.json").exists()
    assert (tmp_path / "artifacts/day23-pack/day23-faq-scorecard.md").exists()
    assert (tmp_path / "artifacts/day23-pack/day23-objection-response-matrix.md").exists()
    assert (tmp_path / "artifacts/day23-pack/day23-adoption-playbook.md").exists()
    assert (tmp_path / "artifacts/day23-pack/day23-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day23-pack/evidence/day23-execution-summary.json").exists()


def test_day23_faq_strict_fails_when_required_sections_missing(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    (tmp_path / "docs/integrations-faq-objections.md").write_text("# FAQ and objections (Day 23)\n", encoding="utf-8")

    rc = fqo.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 1


def test_day23_cli_dispatch(tmp_path: Path, capsys) -> None:
    _write_fixture(tmp_path)

    rc = cli.main(["faq-objections", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 23 FAQ objections" in capsys.readouterr().out
