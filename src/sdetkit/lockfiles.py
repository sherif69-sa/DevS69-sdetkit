"""Which Python lockfiles a repository has, and the exact versions they pin.

One answer for every command: `repo check`'s dependency hygiene, the release readiness
score, and the security gate's offline vulnerability scan and SBOM all read this module,
so a uv or Poetry project is recognised everywhere or nowhere.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# Lockfiles that pin the full Python dependency tree, in the order they are reported.
PYTHON_LOCKFILES = (
    "uv.lock",
    "poetry.lock",
    "pdm.lock",
    "Pipfile.lock",
    "requirements.lock",
    "requirements.txt.lock",
)
# Requirement files whose `name==version` lines also pin packages.
_REQUIREMENT_FILES = ("requirements.lock", "requirements.txt.lock", "requirements.txt")
# TOML lockfiles made of [[package]] tables with `name` and `version` keys.
_PACKAGE_TABLE_LOCKFILES = ("uv.lock", "poetry.lock", "pdm.lock")

_REQUIREMENT = re.compile(r"([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.\-]+)")
_TOML_STRING = re.compile(r'^(name|version)\s*=\s*"([^"]*)"')


@dataclass(frozen=True, order=True)
class PinnedPackage:
    path: str
    line: int
    name: str
    version: str


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def python_lockfiles(root: Path) -> list[str]:
    """The Python lockfiles present at the repository root."""

    return [rel for rel in PYTHON_LOCKFILES if (root / rel).is_file()]


def _from_requirements(rel: str, text: str) -> list[PinnedPackage]:
    pins: list[PinnedPackage] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _REQUIREMENT.match(line)
        if match:
            pins.append(PinnedPackage(rel, line_no, normalize_name(match[1]), match[2]))
    return pins


def _from_package_tables(rel: str, text: str) -> list[PinnedPackage]:
    """Read [[package]] name/version pairs line by line, keeping each package's line."""

    pins: list[PinnedPackage] = []
    current: dict[str, str] | None = None
    start = 0

    def flush() -> None:
        # The project itself (uv's editable or virtual source) is not a dependency.
        if current and "name" in current and "version" in current and not current.get("local"):
            pins.append(
                PinnedPackage(rel, start, normalize_name(current["name"]), current["version"])
            )

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("["):
            flush()
            current, start = ({}, line_no) if line == "[[package]]" else (None, 0)
            continue
        if current is None:
            continue
        match = _TOML_STRING.match(line)
        if match and match[1] not in current:
            current[match[1]] = match[2]
        elif line.startswith("source") and ("editable" in line or "virtual" in line):
            current["local"] = "1"
    flush()
    return pins


def _from_pipfile_lock(rel: str, text: str) -> list[PinnedPackage]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    pins: list[PinnedPackage] = []
    for section in ("default", "develop"):
        packages = data.get(section) if isinstance(data, dict) else None
        if not isinstance(packages, dict):
            continue
        for name, spec in sorted(packages.items()):
            version = spec.get("version", "") if isinstance(spec, dict) else ""
            if isinstance(version, str) and version.startswith("=="):
                pins.append(PinnedPackage(rel, 1, normalize_name(name), version[2:]))
    return pins


def pinned_python_packages(root: Path) -> list[PinnedPackage]:
    """Every exact `name==version` pin in the root's lockfiles and requirement files."""

    pins: list[PinnedPackage] = []
    for rel in sorted({*PYTHON_LOCKFILES, *_REQUIREMENT_FILES}):
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if rel in _PACKAGE_TABLE_LOCKFILES:
            pins.extend(_from_package_tables(rel, text))
        elif rel == "Pipfile.lock":
            pins.extend(_from_pipfile_lock(rel, text))
        else:
            pins.extend(_from_requirements(rel, text))
    return sorted(pins)
