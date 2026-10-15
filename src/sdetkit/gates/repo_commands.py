"""How a repository itself runs a check, read from its pre-commit and tox configuration.

The gate prefers a repository's declared policy to SDETKit's defaults. When mypy is
configured without ``files`` the gate used to run ``mypy src``, a command some projects
never run (python-attrs/attrs type-checks only its ``.pyi`` stubs, from tox); and it ran
``ruff format --check`` over ``src`` and ``tests`` even when the repository's pre-commit
hook excludes a file (psf/requests excludes ``tests/test_lowlevel.py``). These helpers
recover the repository's own invocation instead.
"""

from __future__ import annotations

import configparser
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

import yaml

PYTHON_SUFFIXES = (".py", ".pyi")
# mirrors-mypy runs with these arguments unless the hook sets its own.
MIRRORS_MYPY_DEFAULT_ARGS = ("--ignore-missing-imports", "--scroll-output")

_TOX_MYPY = re.compile(r"^(?:[\w.,{}!-]+:\s+)?(?:python\s+-m\s+)?mypy(?:\s+(?P<args>.*))?$")
_POSARGS = re.compile(r"\{posargs(?::(?P<default>[^}]*))?\}")


def _load_pre_commit(root: Path) -> dict[str, Any] | None:
    path = root / ".pre-commit-config.yaml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def pre_commit_hook(root: Path, hook_ids: set[str]) -> dict[str, Any] | None:
    """The first hook in .pre-commit-config.yaml whose id is one of ``hook_ids``."""

    config = _load_pre_commit(root)
    for repo in (config or {}).get("repos") or []:
        for hook in (repo.get("hooks") if isinstance(repo, dict) else None) or []:
            if isinstance(hook, dict) and hook.get("id") in hook_ids:
                return hook
    return None


def _tracked_files(root: Path) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, capture_output=True, timeout=60, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return [name for name in proc.stdout.decode("utf-8", "replace").split("\0") if name]


def _matches(pattern: Any, path: str, *, default: bool) -> bool:
    if not isinstance(pattern, str) or not pattern:
        return default
    try:
        return re.search(pattern, path) is not None
    except re.error:
        return default


def pre_commit_files(root: Path, hook: dict[str, Any]) -> tuple[str, ...] | None:
    """The Python files pre-commit would pass to ``hook`` on ``pre-commit run --all-files``.

    Applies the top-level and the hook's ``files``/``exclude`` regular expressions to the
    tracked files, as pre-commit does. Returns None outside a git repository.
    """

    tracked = _tracked_files(root)
    if tracked is None:
        return None
    top = _load_pre_commit(root) or {}
    selected = [
        path
        for path in tracked
        if path.endswith(PYTHON_SUFFIXES)
        and (root / path).is_file()
        and _matches(top.get("files"), path, default=True)
        and not _matches(top.get("exclude"), path, default=False)
        and _matches(hook.get("files"), path, default=True)
        and not _matches(hook.get("exclude"), path, default=False)
    ]
    return tuple(sorted(selected))


def narrows_files(root: Path, hook: dict[str, Any]) -> bool:
    """Whether pre-commit selects a subset of files for this hook (files/exclude anywhere)."""

    top = _load_pre_commit(root) or {}
    return any(table.get(key) for table in (top, hook) for key in ("files", "exclude"))


def hook_args(hook: dict[str, Any], default: tuple[str, ...]) -> tuple[str, ...]:
    args = hook.get("args")
    if isinstance(args, list) and all(isinstance(arg, str) for arg in args):
        return tuple(args)
    return default


def tox_mypy_commands(root: Path) -> list[tuple[str, ...]]:
    """Each distinct ``mypy ...`` command in tox.ini's ``commands``, in order, as arguments."""

    path = root / "tox.ini"
    if not path.is_file():
        return []
    parser = configparser.RawConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError):
        return []
    found: list[tuple[str, ...]] = []
    for section in parser.sections():
        if not section.startswith("testenv") or not parser.has_option(section, "commands"):
            continue
        for line in parser.get(section, "commands").splitlines():
            match = _TOX_MYPY.match(line.strip())
            if match is None:
                continue
            text = _POSARGS.sub(lambda m: m.group("default") or "", match.group("args") or "")
            if "{" in text:
                continue
            try:
                args = tuple(shlex.split(text))
            except ValueError:
                continue
            if args not in found:
                found.append(args)
    return found
