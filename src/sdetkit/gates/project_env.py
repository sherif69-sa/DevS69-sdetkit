"""The Python environment a repository's own checks run in, and failures that belong to it.

`gate fast` used to run ruff, mypy and pytest with the interpreter SDETKit itself was
installed in. On a fresh clone of a src-layout project that interpreter has neither the
project nor its dependencies, so pytest failed with "No module named <the project>" and
the gate blamed a test file; mypy read whatever stubs that interpreter happened to have
and failed inside site-packages. Both read as NO_SHIP code failures.

This module finds the project's own interpreter (``--python``, then ``.venv`` / ``venv``
in the repository, then Poetry's or Pipenv's environment, then an activated virtualenv)
and recognises failures caused by the environment rather than the code, with the command
that sets the environment up.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ..lockfiles import python_lockfiles

SDETKIT_SOURCE = "sdetkit"
TOOLS = ("ruff", "mypy", "pytest")

_SETUP_COMMANDS = {
    "uv.lock": "uv sync",
    "poetry.lock": "poetry install",
    "pdm.lock": "pdm install",
    "Pipfile.lock": "pipenv install --dev",
}
# Tools that keep the project's environment outside the repository, and how to ask for it.
_ENV_LOCATORS = (
    ("poetry.lock", ("poetry", "env", "info", "--executable")),
    ("Pipfile.lock", ("pipenv", "--py")),
)
_MISSING_MODULE = re.compile(r"No module named '([A-Za-z0-9_.]+)'")
_MYPY_ERROR = re.compile(r"^(?P<path>[^\s:][^:\n]*):\d+(?::\d+)?: error:", re.MULTILINE)
_INSTALLED_PACKAGE_DIRS = {"site-packages", "dist-packages"}
_PROBE = (
    "import importlib.util, sys; print(sys.prefix); "
    "print(' '.join(m for m in sys.argv[1:] if importlib.util.find_spec(m)))"
)


@dataclass(frozen=True)
class ProjectPython:
    """The interpreter that runs the repository's own checks, and where it was found."""

    executable: str
    source: str
    tools: frozenset[str] = frozenset()
    note: str = ""

    @property
    def is_sdetkit(self) -> bool:
        return self.source == SDETKIT_SOURCE

    def runner(self, tool: str) -> list[str]:
        """The command prefix for a tool: the project's copy when it has one, else SDETKit's."""

        if self.is_sdetkit or tool in self.tools:
            return [self.executable, "-m", tool]
        return [sys.executable, "-m", tool]

    def as_dict(self) -> dict[str, str]:
        out = {"python": self.executable, "source": self.source}
        if self.note:
            out["note"] = self.note
        return out


def venv_python(venv: Path) -> Path | None:
    for rel in ("bin/python", "Scripts/python.exe"):
        candidate = venv / rel
        if candidate.is_file():
            return candidate
    return None


def _located_env_python(root: Path) -> tuple[str, str] | None:
    for lockfile, command in _ENV_LOCATORS:
        if not (root / lockfile).is_file() or shutil.which(command[0]) is None:
            continue
        try:
            proc = subprocess.run(
                list(command), cwd=root, capture_output=True, text=True, timeout=60, check=False
            )
        except (OSError, subprocess.SubprocessError):
            continue
        found = proc.stdout.strip().splitlines()[-1:] if proc.returncode == 0 else []
        if found and Path(found[0]).is_file():
            return found[0], command[0]
    return None


def _candidates(
    root: Path, explicit: str | None, environ: Mapping[str, str]
) -> list[tuple[str, str]]:
    if explicit:
        return [(explicit, "--python")]
    found: list[tuple[str, str]] = []
    for name in (".venv", "venv"):
        python = venv_python(root / name)
        if python is not None:
            found.append((str(python), name))
    located = _located_env_python(root) if not found else None
    if located is not None:
        found.append(located)
    active = environ.get("VIRTUAL_ENV", "")
    python = venv_python(Path(active)) if active else None
    if python is not None:
        found.append((str(python), "VIRTUAL_ENV"))
    return found


def _probe(executable: str, root: Path) -> tuple[Path, frozenset[str]] | None:
    """The interpreter's prefix (a venv's python is a symlink to the base one) and its tools."""

    try:
        proc = subprocess.run(
            [executable, "-c", _PROBE, *TOOLS],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = proc.stdout.splitlines()
    if proc.returncode != 0 or not lines:
        return None
    return Path(lines[0]).resolve(), frozenset(" ".join(lines[1:]).split())


def resolve_project_python(
    root: Path, explicit: str | None = None, environ: Mapping[str, str] | None = None
) -> ProjectPython:
    """The repository's own interpreter, falling back to the one SDETKit runs in.

    Raises ValueError when an explicit ``--python`` does not run.
    """

    env = os.environ if environ is None else environ
    own_prefix = Path(sys.prefix).resolve()
    broken: list[str] = []
    for executable, source in _candidates(root, explicit, env):
        probed = _probe(executable, root)
        if probed is None:
            if source == "--python":
                raise ValueError(f"--python {executable} did not run")
            broken.append(f"{source} ({executable})")
            continue
        if probed[0] == own_prefix:
            return ProjectPython(sys.executable, source, frozenset(TOOLS))
        return ProjectPython(executable, source, probed[1])
    note = f"ignored {', '.join(broken)}: the interpreter did not run" if broken else ""
    return ProjectPython(sys.executable, SDETKIT_SOURCE, note=note)


def setup_command(root: Path) -> str:
    """The command that creates the project's environment with its dependencies."""

    for lockfile in python_lockfiles(root):
        if lockfile in _SETUP_COMMANDS:
            return _SETUP_COMMANDS[lockfile]
    if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file():
        return "python -m venv .venv && .venv/bin/python -m pip install -e ."
    if (root / "requirements.txt").is_file():
        return "python -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
    return "python -m venv .venv"


def own_import_names(root: Path) -> set[str]:
    """Top-level import names this repository defines (src layout and flat layout)."""

    names: set[str] = set()
    for base in (root / "src", root):
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            if entry.name in {"tests", "test", "conftest.py", "setup.py"}:
                continue
            if entry.is_dir() and (entry / "__init__.py").is_file():
                names.add(entry.name)
            elif base.name == "src" and entry.suffix == ".py":
                names.add(entry.stem)
    return names


def pytest_environment_problem(output: str, root: Path, env: ProjectPython) -> str | None:
    """Why pytest failing here says nothing about the code, or None when it might."""

    own = own_import_names(root)
    for name in _MISSING_MODULE.findall(output):
        top = name.split(".", 1)[0]
        if top in own:
            return (
                f"pytest could not import this project's own package '{top}': the project is "
                f"not installed in the interpreter the tests ran with ({env.executable})"
            )
        if env.is_sdetkit and top not in TOOLS:
            return (
                f"pytest could not import '{top}': no project environment was found, so the "
                f"tests ran with SDETKit's own interpreter ({env.executable}), which does not "
                "have the project's dependencies"
            )
    return None


def _outside_repo(path_text: str, root: Path) -> bool:
    path = Path(path_text)
    if _INSTALLED_PACKAGE_DIRS & set(path.parts):
        return True
    full = path if path.is_absolute() else root / path
    try:
        full.resolve().relative_to(root.resolve())
    except ValueError:
        return True
    return False


def mypy_environment_problem(output: str, root: Path) -> str | None:
    """Mypy errors that all sit outside the repository come from installed packages."""

    paths = [match["path"] for match in _MYPY_ERROR.finditer(output)]
    if not paths or not all(_outside_repo(path, root) for path in paths):
        return None
    files = ", ".join(dict.fromkeys(paths))
    return (
        f"mypy reported errors only in installed packages, not in this repository ({files}): "
        "it is reading an environment that is not the project's"
    )
