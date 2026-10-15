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

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .._toml import loads as _toml_loads
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
# Requirement files that hold a pip project's test and development dependencies.
_DEV_REQUIREMENTS = (
    "requirements-dev.txt",
    "dev-requirements.txt",
    "requirements/dev.txt",
    "requirements-test.txt",
    "test-requirements.txt",
    "requirements-tests.txt",
    "requirements/test.txt",
    "requirements/tests.txt",
)
# Extras that, by convention, install what the tests need.
_TEST_EXTRAS = ("test", "tests", "testing", "dev")
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
# Which copy of the project an interpreter imports: the installed distribution's version,
# where an editable install points, and where each top-level package resolves from.
_CHECKOUT_PROBE = """
import importlib.metadata as md, importlib.util as iu, json, sys
name, packages = sys.argv[1], sys.argv[2:]
out = {"version": None, "editable": None, "origins": {}}
try:
    dist = md.distribution(name)
except md.PackageNotFoundError:
    dist = None
if dist is not None:
    out["version"] = dist.version
    try:
        direct = json.loads(dist.read_text("direct_url.json") or "null") or {}
    except ValueError:
        direct = {}
    if (direct.get("dir_info") or {}).get("editable"):
        out["editable"] = direct.get("url")
for package in packages:
    try:
        spec = iu.find_spec(package)
    except (ImportError, ValueError):
        spec = None
    out["origins"][package] = spec.origin if spec is not None else None
print(json.dumps(out))
"""


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
    install = ".venv/bin/python -m pip install"
    dev = "".join(f" -r {rel}" for rel in _DEV_REQUIREMENTS if (root / rel).is_file())
    if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file():
        extras = "" if dev else _test_extras(root)
        return f"python -m venv .venv && {install} -e .{extras}{dev}"
    if (root / "requirements.txt").is_file():
        return f"python -m venv .venv && {install} -r requirements.txt{dev}"
    return "python -m venv .venv"


def _test_extras(root: Path) -> str:
    """``[test,dev]``-style extras the project declares for its tests, or ""."""

    try:
        data = _toml_loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    declared = project.get("optional-dependencies")
    names = [name for name in _TEST_EXTRAS if isinstance(declared, dict) and name in declared]
    return f"[{','.join(names)}]" if names else ""


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


def project_identity(root: Path) -> tuple[str, str | None] | None:
    """The project's distribution name and its static version (None when it is dynamic)."""

    try:
        data = _toml_loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    poetry = (data.get("tool") or {}).get("poetry") if isinstance(data.get("tool"), dict) else {}
    for table in (project, poetry if isinstance(poetry, dict) else {}):
        name = table.get("name")
        if isinstance(name, str) and name:
            version = table.get("version")
            dynamic = "version" in (table.get("dynamic") or [])
            return name, version if isinstance(version, str) and not dynamic else None
    return None


def _src_packages(root: Path) -> list[str]:
    src = root / "src"
    if not src.is_dir():
        return []
    return sorted(
        entry.name
        for entry in src.iterdir()
        if entry.is_dir() and (entry / "__init__.py").is_file()
    )


def _inside(path_text: str, root: Path) -> bool:
    try:
        Path(path_text).resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


@dataclass(frozen=True)
class CheckoutProblem:
    """The interpreter that ran the checks does not have this checkout installed.

    ``installed`` is False when the project is not installed there at all (its dependencies
    are missing too, which breaks mypy as well as pytest), and True when another copy of
    the project is installed in its place (only the tests import it).
    """

    reason: str
    installed: bool


def checkout_problem(root: Path, env: ProjectPython) -> CheckoutProblem | None:
    """Why the interpreter that ran the checks does not import this checkout, or None.

    The checkout counts as installed when the project's distribution is an editable install
    of this directory, when its version equals the checkout's static version (a wheel built
    from it), or when every src-layout package resolves inside the repository. A project
    with no name in pyproject.toml is never judged.
    """

    identity = project_identity(root)
    if identity is None:
        return None
    name, static_version = identity
    packages = _src_packages(root)
    try:
        proc = subprocess.run(
            [env.executable, "-c", _CHECKOUT_PROBE, name, *packages],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        probe = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        probe = None
    if not isinstance(probe, dict):
        return None
    version = probe.get("version")
    origins = probe.get("origins") or {}
    if version is None:
        if not env.is_sdetkit:
            return None
        return CheckoutProblem(
            f"{name} is not installed in the interpreter the checks ran with ({env.executable}) "
            "and no project environment was found, so its dependencies are missing there",
            installed=False,
        )
    editable = str(probe.get("editable") or "")
    if editable.startswith("file://") and _inside(editable[len("file://") :], root):
        return None
    if static_version is not None and version == static_version:
        return None
    elsewhere = {
        # An installed copy inside the repository's own .venv is still not the checkout.
        pkg: origin
        for pkg, origin in origins.items()
        if origin and _outside_repo(origin, root)
    }
    if not elsewhere:
        return None
    package, origin = sorted(elsewhere.items())[0]
    return CheckoutProblem(
        f"the tests imported {name} {version} installed at {origin}, not this checkout "
        f"('{package}' resolves outside the repository in {env.executable})",
        installed=True,
    )
