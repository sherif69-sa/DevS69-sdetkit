from __future__ import annotations

from pathlib import Path

import tomllib


def test_releasing_doc_and_hero_badge_match_pyproject_version() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = str(pyproject["project"]["version"])
    version_tag = f"v{project_version}"

    releasing = (repo_root / "docs" / "releasing.md").read_text(encoding="utf-8")
    assert f"Current baseline release: **{version_tag}**." in releasing

    hero_svg = (repo_root / "docs" / "assets" / "devs69-hero.svg").read_text(encoding="utf-8")
    assert version_tag in hero_svg
