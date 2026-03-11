from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/release_preflight.py").resolve()


def _write_baseline(root: Path, version: str = "1.2.3") -> tuple[Path, Path]:
    pyproject = root / "pyproject.toml"
    changelog = root / "CHANGELOG.md"
    pyproject.write_text(f"[project]\nname='x'\nversion='{version}'\n", encoding="utf-8")
    changelog.write_text(f"## Unreleased\n\n## [{version}]\n- note\n", encoding="utf-8")
    return pyproject, changelog


def _run(pyproject: Path, changelog: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--pyproject",
            str(pyproject),
            "--changelog",
            str(changelog),
            *args,
        ],
        check=False,
        text=True,
        capture_output=True,
    )


def test_release_preflight_ok_with_tag(tmp_path: Path) -> None:
    pyproject, changelog = _write_baseline(tmp_path)
    proc = _run(pyproject, changelog, "--tag", "v1.2.3")
    assert proc.returncode == 0


def test_release_preflight_fails_on_bad_tag_format(tmp_path: Path) -> None:
    pyproject, changelog = _write_baseline(tmp_path)
    proc = _run(pyproject, changelog, "--tag", "1.2.3")
    assert proc.returncode == 1


def test_release_preflight_fails_without_changelog_heading(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    changelog = tmp_path / "CHANGELOG.md"
    pyproject.write_text("[project]\nname='x'\nversion='1.2.3'\n", encoding="utf-8")
    changelog.write_text("## Unreleased\n", encoding="utf-8")
    proc = _run(pyproject, changelog)
    assert proc.returncode == 1
