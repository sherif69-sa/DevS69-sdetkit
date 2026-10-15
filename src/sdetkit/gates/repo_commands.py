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

PYTHON_SUFFIXES = (".py", ".pyi")
# mirrors-mypy runs with these arguments unless the hook sets its own.
MIRRORS_MYPY_DEFAULT_ARGS = ("--ignore-missing-imports", "--scroll-output")

_TOX_MYPY = re.compile(r"^(?:[\w.,{}!-]+:\s+)?(?:python\s+-m\s+)?mypy(?:\s+(?P<args>.*))?$")
_POSARGS = re.compile(r"\{posargs(?::(?P<default>[^}]*))?\}")


_KEY = re.compile(r"^(?P<indent>\s*)(?P<dash>-\s+)?(?P<key>[A-Za-z_][\w-]*):(?:\s+(?P<value>.*))?$")
_PRE_COMMIT_KEYS = {"files", "exclude", "args", "id", "pass_filenames"}


def _unquote(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'")
    if len(text) >= 2 and text[0] == text[-1] == '"':
        inner = text[1:-1]
        return re.sub(r'\\([\\"])', r"\1", inner)
    return text


def _strip_comment(text: str) -> str:
    quote = ""
    for index, char in enumerate(text):
        if quote:
            quote = "" if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char == "#" and (index == 0 or text[index - 1].isspace()):
            return text[:index].rstrip()
    return text.rstrip()


def _flow_list(text: str) -> list[str]:
    """Split ``[a, 'b,c', "d"]`` on the commas that are outside quotes."""

    items: list[str] = []
    current, quote = "", ""
    for char in text.strip()[1:-1]:
        if quote:
            quote = "" if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char == ",":
            items.append(current)
            current = ""
            continue
        current += char
    items.append(current)
    return [_unquote(item) for item in items if item.strip()]


def read_pre_commit(text: str) -> dict[str, Any]:
    """The parts of a pre-commit config the gate reads, without a YAML dependency.

    Returns the top-level ``files``/``exclude`` and a ``hooks`` list of dicts with each
    hook's ``id``, ``files``, ``exclude``, ``args`` and ``pass_filenames``. Block scalars (``|``, ``>``), flow
    and block lists, quoting and comments are handled; anything else is ignored.
    """

    lines = text.splitlines()
    top: dict[str, Any] = {}
    hooks: list[dict[str, Any]] = []
    item: dict[str, Any] | None = None
    item_col = -1
    index = 0
    while index < len(lines):
        raw = lines[index]
        index += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = _KEY.match(_strip_comment(raw))
        if match is None:
            continue
        col = len(match["indent"]) + len(match["dash"] or "")
        key, value = match["key"], (match["value"] or "").strip()
        if match["dash"]:
            item = {}
            item_col = col
            hooks.append(item)
        elif col != item_col:
            item = None if col < item_col else item
        if value.startswith(("|", ">")):
            block: list[str] = []
            while index < len(lines) and (
                not lines[index].strip() or len(lines[index]) - len(lines[index].lstrip()) > col
            ):
                block.append(lines[index].strip())
                index += 1
            joiner = "\n" if value.startswith("|") else " "
            value_any: Any = joiner.join(block).strip()
        elif value.startswith("["):
            value_any = _flow_list(value)
        elif not value:
            values: list[str] = []
            while index < len(lines):
                nxt = _strip_comment(lines[index])
                stripped = nxt.strip()
                # A `- item` line is a list value; a `- key: value` line starts a mapping.
                if (
                    stripped.startswith("- ")
                    and len(nxt) - len(nxt.lstrip()) >= col
                    and _KEY.match(nxt) is None
                ):
                    values.append(_unquote(stripped[2:]))
                    index += 1
                    continue
                break
            value_any = values if values else None
        else:
            value_any = _unquote(value)
        if col == 0 and not match["dash"] and key in {"files", "exclude"}:
            top[key] = value_any
        elif item is not None and col == item_col and key in _PRE_COMMIT_KEYS:
            item[key] = value_any
    top["hooks"] = [hook for hook in hooks if isinstance(hook.get("id"), str)]
    return top


def _load_pre_commit(root: Path) -> dict[str, Any] | None:
    path = root / ".pre-commit-config.yaml"
    try:
        return read_pre_commit(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, UnicodeDecodeError):
        return None


def pre_commit_hook(root: Path, hook_ids: set[str]) -> dict[str, Any] | None:
    """The first hook in .pre-commit-config.yaml whose id is one of ``hook_ids``."""

    for hook in (_load_pre_commit(root) or {}).get("hooks") or []:
        if hook.get("id") in hook_ids:
            return dict(hook)
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


def passes_filenames(hook: dict[str, Any]) -> bool:
    """False when the hook runs its command as is (``pass_filenames: false``)."""

    return str(hook.get("pass_filenames", True)).strip().lower() not in {"false", "no", "off"}


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
