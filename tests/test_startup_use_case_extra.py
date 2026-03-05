from __future__ import annotations

from pathlib import Path

from sdetkit import startup_use_case as suc


def test_write_defaults_noop_when_page_valid(tmp_path: Path) -> None:
    page = tmp_path / "docs/use-cases-startup-small-team.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(suc._DAY12_DEFAULT_PAGE, encoding="utf-8")
    assert suc._write_defaults(tmp_path) == []


def test_main_markdown_output_and_emit_pack(tmp_path: Path) -> None:
    out = tmp_path / "out.md"
    rc = suc.main(
        [
            "--root",
            str(tmp_path),
            "--write-defaults",
            "--emit-pack-dir",
            "docs/artifacts/day12-pack",
            "--format",
            "markdown",
            "--output",
            str(out),
            "--strict",
        ]
    )
    assert rc == 0
    assert out.exists()
    risk = tmp_path / "docs/artifacts/day12-pack/startup-day12-risk-register.md"
    assert risk.exists()


def test_main_strict_fails_when_missing(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/use-cases-startup-small-team.md").write_text("# short\n", encoding="utf-8")
    assert suc.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1
