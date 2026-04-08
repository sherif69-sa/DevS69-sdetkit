from __future__ import annotations

from pathlib import Path


README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
DOCS_COMMAND_SURFACE = Path("docs/command-surface.md")
DOCS_STABILITY = Path("docs/stability-levels.md")
DOCS_VERSIONING = Path("docs/versioning-and-support.md")

CANONICAL_PATH = (
    "python -m sdetkit gate fast",
    "python -m sdetkit gate release",
    "python -m sdetkit doctor",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readme_and_docs_home_share_primary_identity_language() -> None:
    readme = _text(README)
    docs_home = _text(DOCS_INDEX)

    required = (
        "release-confidence CLI",
        "Primary outcome:",
        "Canonical first path:",
    )

    for marker in required:
        assert marker in readme
        assert marker in docs_home



def test_front_door_and_reference_docs_keep_canonical_path_obvious() -> None:
    pages = (README, DOCS_INDEX, DOCS_CLI, DOCS_COMMAND_SURFACE, DOCS_VERSIONING)

    for page in pages:
        content = _text(page)
        for command in CANONICAL_PATH:
            assert command in content, f"missing canonical path command in {page}: {command}"



def test_secondary_material_is_explicitly_demoted_from_front_door() -> None:
    readme = _text(README)
    docs_home = _text(DOCS_INDEX)
    command_surface = _text(DOCS_COMMAND_SURFACE)
    stability = _text(DOCS_STABILITY)

    assert "Historical and transition-era references (secondary)" in readme
    assert "intentionally secondary to first-time adoption" in docs_home
    assert "intentionally secondary to first proof" in command_surface
    assert "single primary identity" in stability
