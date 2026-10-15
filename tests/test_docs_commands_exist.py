"""Published docs only name commands, scripts and make targets that exist."""

from __future__ import annotations

import contextlib
import fnmatch
import importlib
import importlib.util
import io
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from sdetkit._toml import loads as toml_loads
from sdetkit.cli import COMMANDS, SUBCOMMANDS

ROOT = Path(__file__).resolve().parents[1]
ENTRY_FILES = ("README.md", "CONTRIBUTING.md")

CMD_RE = re.compile(
    r"(?:python -m sdetkit|(?<![\w./-])sdetkit) ([a-z][a-z0-9-]*)(?: ([a-z][a-z0-9-]*))?"
)
MAKE_RE = re.compile(r"(?:^|&&|;|\|)\s*make ([a-z][a-z0-9-]+)", re.M)
SCRIPT_RE = re.compile(
    r"(?:python3? |bash |\./)(?:\.\./)*((?:(?:scripts|tools)/)?[A-Za-z0-9_-]+"
    r"(?:/[A-Za-z0-9_-]+)*\.(?:py|sh))\b"
)
MODULE_RE = re.compile(r"python3? -m (sdetkit(?:\.[A-Za-z0-9_]+)+)")
CONSOLE_RE = re.compile(r"(?m)^\s*(sdetkit-[a-z][a-z0-9-]*)\s")
# Words that follow "sdetkit" in quoted messages rather than commands.
PROSE_WORDS = frozenset({"requires"})


def _excluded(path: str, rules: list[str]) -> bool:
    out = False
    for rule in rules:
        negate = rule.startswith("!")
        pattern = rule[1:] if negate else rule
        if pattern.startswith("/"):
            hit = path == pattern[1:]
        elif pattern.endswith("/**"):
            hit = path.startswith(pattern[:-2])
        else:
            hit = fnmatch.fnmatch(path.rsplit("/", 1)[-1], pattern) or fnmatch.fnmatch(
                path, pattern
            )
        if hit:
            out = not negate
    return out


def _published_files() -> list[str]:
    # mkdocs.yml uses !!python/name tags; drop them so the config loads safely.
    text = re.sub(r"!!python/[a-z]+:", "", (ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
    config = yaml.safe_load(text)
    rules = [line.strip() for line in str(config["exclude_docs"]).splitlines() if line.strip()]
    tracked = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    return [
        path
        for path in tracked
        if (path.startswith("docs/") and not _excluded(path[5:], rules)) or path in ENTRY_FILES
    ]


def _code(text: str) -> tuple[str, str]:
    """Fenced blocks and inline code spans: where docs tell people what to run."""

    fences = re.findall(r"(?ms)^```[^\n]*\n(.*?)^```", text)
    spans = re.findall(r"`([^`\n]+)`", re.sub(r"(?ms)^```.*?^```", "", text))
    return "\n".join(fences + spans), "\n".join(fences)


_CHOICES: dict[str, set[str] | None] = {}


def _subcommands(command: str) -> set[str] | None:
    """Subcommands an argparse-based command accepts, read from its help (None if none)."""

    if command not in _CHOICES:
        spec = COMMANDS[command]
        module = importlib.import_module(spec.module)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                module.main([*spec.prefix, "--help"])
            except SystemExit:
                pass
        usage = out.getvalue().split("\n\n", 1)[0]
        match = re.search(r"\{([a-z0-9_,-]+)\}", usage)
        _CHOICES[command] = set(match.group(1).split(",")) if match else None
    return _CHOICES[command]


def _module_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _missing(text: str) -> list[str]:
    code, fences = _code(text)
    targets = set(re.findall(r"(?m)^([a-z][a-z0-9-]*):", (ROOT / "Makefile").read_text()))
    pyproject = toml_loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    console_scripts = set(pyproject["project"].get("scripts", {}))
    missing: set[str] = set()
    for match in CMD_RE.finditer(code):
        command, sub = match.group(1), match.group(2)
        line = code[code.rfind("\n", 0, match.start()) + 1 : match.start()]
        if command in PROSE_WORDS or re.search(r"pip install|import |from $", line):
            continue
        if command not in COMMANDS:
            missing.add(f"sdetkit {command}")
        elif command in SUBCOMMANDS:
            if sub and sub not in SUBCOMMANDS[command]:
                missing.add(f"sdetkit {command} {sub}")
        elif sub:
            choices = _subcommands(command)
            if choices is not None and sub not in choices:
                missing.add(f"sdetkit {command} {sub}")
    missing |= {f"make {t}" for t in MAKE_RE.findall(code) if t not in targets}
    missing |= {path for path in SCRIPT_RE.findall(code) if not (ROOT / path).is_file()}
    missing |= {f"python -m {m}" for m in MODULE_RE.findall(code) if not _module_exists(m)}
    missing |= {name for name in CONSOLE_RE.findall(fences) if name not in console_scripts}
    return sorted(missing)


@pytest.mark.parametrize("path", _published_files())
def test_published_docs_only_name_things_that_exist(path: str) -> None:
    assert _missing((ROOT / path).read_text(encoding="utf-8")) == []


def test_the_checker_catches_removed_commands() -> None:
    text = (
        "```bash\n"
        "python -m sdetkit agent run x\n"
        "python -m sdetkit diagnose nope\n"
        "python -m sdetkit kits nope\n"
        "make no-such-target\n"
        "python scripts/no_such_script.py\n"
        "python -m sdetkit.no_such_module\n"
        "sdetkit-no-such-console-script --x\n"
        "python -m pip install sdetkit ruff\n"
        "```\n"
        "Inline `python -m sdetkit gate fast` and `make gate-fast` are fine.\n"
    )

    assert _missing(text) == [
        "make no-such-target",
        "python -m sdetkit.no_such_module",
        "scripts/no_such_script.py",
        "sdetkit agent",
        "sdetkit diagnose nope",
        "sdetkit kits nope",
        "sdetkit-no-such-console-script",
    ]
