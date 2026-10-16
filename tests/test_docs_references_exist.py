"""Every repository path and make target the published pages cite exists.

A full read of the site found pages citing 24 GitHub workflows that were retired, scripts
(`scripts/check.sh`, `check_canonical_path_drift.py`, `release_verify_post_publish.py`),
make targets (`make release-verify-plan`) and a `src/sdetkit/cli.py` that became a package.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PATH = re.compile(
    r"`((?:scripts|tools|\.github/workflows|\.github/actions|src/sdetkit)/[A-Za-z0-9_./-]+?)`"
)
MAKE = re.compile(r"`make ([a-z][a-z0-9-]*)`|^\s*make ([a-z][a-z0-9-]*)\s*$", re.M)


def _nav_pages() -> list[Path]:
    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("", lambda loader, suffix, node: None)
    # A SafeLoader that ignores mkdocs.yml's `!!python/name:` tags.
    nav = Loader((ROOT / "mkdocs.yml").read_text(encoding="utf-8")).get_single_data()["nav"]
    pages: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, str) and node.endswith(".md"):
            pages.append(node)

    walk(nav)
    return [ROOT / "docs" / page for page in pages if (ROOT / "docs" / page).is_file()]


def _make_targets() -> set[str]:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    return set(re.findall(r"^([a-z][a-z0-9-]*):", text, re.M))


def test_cited_repository_paths_exist() -> None:
    missing = [
        f"{page.relative_to(ROOT)}: {ref}"
        for page in _nav_pages()
        for ref in PATH.findall(page.read_text(encoding="utf-8"))
        if not any(ch in ref for ch in "*<{") and not (ROOT / ref.rstrip("/.")).exists()
    ]

    assert missing == []


def test_cited_make_targets_exist() -> None:
    targets = _make_targets()
    missing = [
        f"{page.relative_to(ROOT)}: make {name}"
        for page in _nav_pages()
        for match in MAKE.finditer(page.read_text(encoding="utf-8"))
        for name in [match[1] or match[2]]
        if name not in targets
    ]

    assert missing == []
