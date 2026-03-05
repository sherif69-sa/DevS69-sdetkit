from __future__ import annotations

import json
from pathlib import Path

from sdetkit import first_contribution as fc


def test_write_defaults_and_main_markdown_output(tmp_path: Path) -> None:
    out = tmp_path / "artifacts/day10.md"
    rc = fc.main(
        [
            "--root",
            str(tmp_path),
            "--write-defaults",
            "--format",
            "markdown",
            "--output",
            str(out),
            "--strict",
        ]
    )
    assert rc == 0
    assert out.exists()
    assert (tmp_path / "CONTRIBUTING.md").exists()


def test_write_defaults_noop_when_header_present(tmp_path: Path) -> None:
    c = tmp_path / "CONTRIBUTING.md"
    c.write_text(fc._DAY10_DEFAULT_BLOCK, encoding="utf-8")
    assert fc._write_defaults(tmp_path) == []


def test_main_json_strict_fail(tmp_path: Path, capsys) -> None:
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n", encoding="utf-8")
    rc = fc.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["missing"]
