"""Per-repository configuration for ``sdetkit gate fast``.

The gate enforces the policy a repository declares, not SDETKit's own
conventions. Each step resolves its command from (highest precedence first):

1. explicit CLI flags (``--pytest-args``, ``--mypy-args``, ``--full-pytest``, ``--only``),
2. ``[tool.sdetkit.gate]`` in ``pyproject.toml``,
3. auto-detection of the repository's own tool configuration.

A step whose tool the repository does not configure is skipped with a recorded
reason instead of failing with errors that have nothing to do with the change.
Selecting a step explicitly (``--only <step>``) forces it to run.
"""

from __future__ import annotations

import configparser
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .._toml import loads as _toml_loads
from ..repo_model import RepoModel, TestSuite
from .repo_commands import (
    MIRRORS_MYPY_DEFAULT_ARGS,
    hook_args,
    narrows_files,
    passes_filenames,
    pre_commit_files,
    pre_commit_hook,
    tox_mypy_commands,
)

DEFAULT_DOCTOR_ARGS: tuple[str, ...] = ("--dev", "--deps", "--clean-tree")
_TEST_DIR_NAMES = ("tests", "test")
_DEFAULT_SOURCE_PATHS = ("src", "tests")


@dataclass(frozen=True)
class StepPlan:
    """Resolved arguments for one gate step, or the reason it is skipped."""

    args: tuple[str, ...] = ()
    skip_reason: str = ""
    # Further invocations after ``args`` (a repository that runs the tool more than once).
    more: tuple[tuple[str, ...], ...] = ()
    # Where the arguments came from when the repository's own configuration supplied them.
    source: str = ""

    @property
    def skipped(self) -> bool:
        return bool(self.skip_reason)


@dataclass(frozen=True)
class GateConfig:
    pytest_args: tuple[str, ...] | None = None
    mypy_args: tuple[str, ...] | None = None
    ruff_paths: tuple[str, ...] | None = None
    doctor_args: tuple[str, ...] = DEFAULT_DOCTOR_ARGS
    ci_templates: bool = False
    errors: tuple[str, ...] = field(default_factory=tuple)


def _read_pyproject(root: Path) -> dict[str, Any]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return {}
    try:
        data = _toml_loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _tool_table(pyproject: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    node: Any = pyproject.get("tool")
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node if isinstance(node, dict) else None


def _str_list(raw: Any, key: str, errors: list[str]) -> tuple[str, ...] | None:
    if raw is None:
        return None
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return tuple(raw)
    errors.append(f"[tool.sdetkit.gate] {key} must be a list of strings")
    return None


def load_gate_config(root: Path) -> GateConfig:
    table = _tool_table(_read_pyproject(root), "sdetkit", "gate") or {}
    errors: list[str] = []
    doctor_args = _str_list(table.get("doctor_args"), "doctor_args", errors)
    ci_templates = table.get("ci_templates", False)
    if not isinstance(ci_templates, bool):
        errors.append("[tool.sdetkit.gate] ci_templates must be a boolean")
        ci_templates = False
    return GateConfig(
        pytest_args=_str_list(table.get("pytest_args"), "pytest_args", errors),
        mypy_args=_str_list(table.get("mypy_args"), "mypy_args", errors),
        ruff_paths=_str_list(table.get("ruff_paths"), "ruff_paths", errors),
        doctor_args=doctor_args if doctor_args is not None else DEFAULT_DOCTOR_ARGS,
        ci_templates=ci_templates,
        errors=tuple(errors),
    )


def _ini_has_section(path: Path, *sections: str) -> bool:
    if not path.is_file():
        return False
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError):
        return False
    return any(parser.has_section(section) for section in sections)


def has_tests(root: Path) -> bool:
    if any((root / name).is_dir() for name in _TEST_DIR_NAMES):
        return True
    if (root / "conftest.py").is_file() or (root / "pytest.ini").is_file():
        return True
    if _tool_table(_read_pyproject(root), "pytest", "ini_options") is not None:
        return True
    if _ini_has_section(root / "setup.cfg", "tool:pytest"):
        return True
    if _ini_has_section(root / "tox.ini", "pytest"):
        return True
    return any(root.glob("test_*.py")) or any(root.glob("*_test.py"))


def ruff_configured(root: Path) -> bool:
    if (root / "ruff.toml").is_file() or (root / ".ruff.toml").is_file():
        return True
    if _tool_table(_read_pyproject(root), "ruff") is not None:
        return True
    pre_commit = root / ".pre-commit-config.yaml"
    if pre_commit.is_file():
        try:
            return "ruff" in pre_commit.read_text(encoding="utf-8")
        except OSError:
            return False
    return False


def _mypy_config(root: Path) -> tuple[bool, bool]:
    """Return ``(configured, declares_files)`` for the repository's mypy setup."""

    table = _tool_table(_read_pyproject(root), "mypy")
    if table is not None:
        return True, "files" in table
    for name, section in (("mypy.ini", "mypy"), (".mypy.ini", "mypy"), ("setup.cfg", "mypy")):
        path = root / name
        if not _ini_has_section(path, section):
            continue
        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        return True, parser.has_option(section, "files")
    return False, False


def plan_pytest(
    root: Path,
    config: GateConfig,
    cli_args: str | None,
    full: bool,
    *,
    force: bool = False,
    model: RepoModel | None = None,
) -> StepPlan:
    if cli_args:
        return StepPlan(tuple(shlex.split(cli_args)))
    if full:
        return StepPlan(("-q",))
    if config.pytest_args is not None:
        return StepPlan(config.pytest_args)
    if not force and model is not None and model.other_languages and not model.has_python:
        return StepPlan(
            skip_reason="no Python detected (repository languages: "
            + ", ".join(model.other_languages)
            + ")"
        )
    if not force and not has_tests(root):
        return StepPlan(skip_reason="no tests detected (tests/, test/, or pytest config)")
    return StepPlan(("-q",))


def plan_suite(root: Path, suite: TestSuite) -> StepPlan:
    """Run a non-Python workspace's own test chain, or say why it cannot run here."""

    workdir = root / suite.working_directory
    if not workdir.is_dir():
        return StepPlan(skip_reason=f"working directory {suite.working_directory} is missing")
    for argv in suite.argv():
        executable = argv[0] if argv else ""
        local = "/" in executable and (workdir / executable).is_file()
        if not executable or not (local or shutil.which(executable)):
            return StepPlan(skip_reason=f"{executable or 'command'} is not installed")
    return StepPlan(suite.commands)


def plan_mypy(
    root: Path, config: GateConfig, cli_args: str | None, *, force: bool = False
) -> StepPlan:
    if cli_args:
        return StepPlan(tuple(shlex.split(cli_args)))
    if config.mypy_args is not None:
        return StepPlan(config.mypy_args)
    configured, declares_files = _mypy_config(root)
    if not configured and not force:
        return StepPlan(skip_reason="mypy is not configured (pyproject [tool.mypy] or mypy.ini)")
    if declares_files:
        return StepPlan(())
    # No `files`: run mypy the way the repository runs it, before falling back to `src`.
    hook = pre_commit_hook(root, {"mypy"})
    if hook is not None and not passes_filenames(hook):
        # `pass_filenames: false`: pre-commit runs the hook's arguments as they are.
        args = hook_args(hook, ())
        if any(not arg.startswith("-") for arg in args):
            return StepPlan(args, source="pre-commit mypy hook")
    elif hook is not None:
        files = pre_commit_files(root, hook)
        if files:
            return StepPlan(
                (*hook_args(hook, MIRRORS_MYPY_DEFAULT_ARGS), *files),
                source="pre-commit mypy hook",
            )
    tox_commands = [args for args in tox_mypy_commands(root) if args]
    if tox_commands:
        return StepPlan(tox_commands[0], more=tuple(tox_commands[1:]), source="tox.ini")
    return StepPlan(("src",) if (root / "src").is_dir() else (".",))


_RUFF_HOOKS = {"check": {"ruff", "ruff-check"}, "format": {"ruff-format"}}


def plan_ruff(
    root: Path, config: GateConfig, *, force: bool = False, command: str = "check"
) -> StepPlan:
    if config.ruff_paths is not None:
        return StepPlan(config.ruff_paths)
    if not force and not ruff_configured(root):
        return StepPlan(skip_reason="ruff is not configured (pyproject [tool.ruff] or ruff.toml)")
    hook = pre_commit_hook(root, _RUFF_HOOKS.get(command, set()))
    if hook is not None and passes_filenames(hook) and narrows_files(root, hook):
        # The repository's pre-commit hook excludes files: check exactly what it checks.
        files = pre_commit_files(root, hook)
        label = f"pre-commit {hook.get('id')} hook"
        if files == ():
            return StepPlan(skip_reason=f"the {label} selects no Python files")
        if files is not None:
            return StepPlan(("--force-exclude", *files), source=label)
    existing = tuple(path for path in _DEFAULT_SOURCE_PATHS if (root / path).exists())
    return StepPlan(existing or (".",))
