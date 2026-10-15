"""What counts as an uncommitted change when SDETKit judges a working tree.

Running SDETKit and the repository's own tests leaves untracked files behind: SDETKit's
workspace under ``.sdetkit/``, reports under ``build/``, and Python and tool caches. They
are not changes to the code being released, so they must not turn a clean tree dirty (a
second ``gate release`` would otherwise refuse to ship because of the first one). Tracked
files always count, wherever they live.
"""

from __future__ import annotations

# Untracked paths under these prefixes are SDETKit's own outputs.
OUTPUT_PREFIXES = (".sdetkit/", "build/")
# Untracked paths with one of these components are caches written by running Python tools.
CACHE_DIRS = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis"}
)


def is_tool_output(path: str) -> bool:
    """True for a path SDETKit or a test run writes on its own."""

    if path.startswith(OUTPUT_PREFIXES) or path.endswith(".pyc"):
        return True
    return any(part in CACHE_DIRS for part in path.split("/"))


def uncommitted_changes(porcelain: str) -> list[str]:
    """The ``git status --porcelain`` entries that are real uncommitted changes."""

    changes: list[str] = []
    for entry in porcelain.splitlines():
        if not entry.strip():
            continue
        if entry.startswith("?? ") and is_tool_output(entry[3:].strip()):
            continue
        changes.append(entry)
    return changes
