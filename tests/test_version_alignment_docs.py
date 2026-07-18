from __future__ import annotations

import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility
    import tomli as tomllib


def test_release_docs_align_public_and_candidate_versions() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = str(pyproject["project"]["version"])
    delta = json.loads(
        (repo_root / "docs/contracts/current-product-delta.v1.json").read_text(encoding="utf-8")
    )
    released_version = str(delta["released_version"])
    candidate_version = str(delta["release_candidate_version"])

    assert project_version == candidate_version

    releasing = (repo_root / "docs/releasing.md").read_text(encoding="utf-8")
    assert f"Current baseline release: **v{released_version}**." in releasing

    hero_svg = (repo_root / "docs/assets/devs69-hero.svg").read_text(encoding="utf-8")
    assert f"v{released_version}" in hero_svg
    if candidate_version != released_version:
        assert f"v{candidate_version}" not in hero_svg
