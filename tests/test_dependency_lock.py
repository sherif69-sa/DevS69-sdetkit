"""uv.lock is a real lock of pyproject.toml and agrees with the CI pins.

CI runs `uv lock --check` (needs network); these checks run offline.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from sdetkit._toml import loads as toml_loads

ROOT = Path(__file__).resolve().parents[1]
# Tools CI installs that are not dependencies of the project.
NOT_LOCKED = frozenset({"uv"})


def _load(name: str) -> dict:
    return toml_loads((ROOT / name).read_text(encoding="utf-8"))


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _locked_versions() -> dict[str, set[str]]:
    versions: dict[str, set[str]] = {}
    for package in _load("uv.lock")["package"]:
        versions.setdefault(package["name"], set()).add(package["version"])
    return versions


def test_uv_lock_locks_this_project() -> None:
    project = _load("pyproject.toml")["project"]
    lock = _load("uv.lock")
    root = [p for p in lock["package"] if p.get("source") == {"editable": "."}]

    assert not (ROOT / "poetry.lock").exists()
    assert lock["requires-python"] == project["requires-python"]
    assert [(p["name"], p["version"]) for p in root] == [(project["name"], project["version"])]
    assert set(root[0]["optional-dependencies"]) == set(project["optional-dependencies"])
    assert len(lock["package"]) > len(project["dependencies"])


def test_ci_pins_match_the_lock() -> None:
    locked = _locked_versions()
    pins = re.findall(
        r"(?m)^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==([^\s;#]+)",
        (ROOT / "constraints-ci.txt").read_text(encoding="utf-8"),
    )
    mismatched = [
        f"{name}=={version} (locked: {sorted(locked.get(_normalize(name), ())) or 'missing'})"
        for name, version in pins
        if _normalize(name) not in NOT_LOCKED and version not in locked.get(_normalize(name), ())
    ]

    assert pins
    assert mismatched == [], "constraints-ci.txt and uv.lock disagree; run `make lock`"


def test_make_lock_and_the_dependabot_job_share_one_refresh() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/dependency-auto-merge.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"]["refresh-lock"]
    steps = {step.get("name", step.get("uses", "")): step for step in job["steps"]}

    make_lock = makefile.split("\nlock:", 1)[1].split("\n\n")[0]
    assert "bash scripts/refresh_uv_lock.sh" in make_lock
    assert "bash scripts/refresh_uv_lock.sh" in steps["Refresh uv.lock"]["run"]
    assert "python scripts/sync_pre_commit_revs.py" in make_lock
    assert "python scripts/sync_pre_commit_revs.py" in steps["Refresh uv.lock"]["run"]
    assert job["if"].startswith("github.actor == 'dependabot[bot]'")
    # A push with GITHUB_TOKEN would not start CI: push only with the secret.
    assert "HAS_LOCK_TOKEN == 'true'" in steps["Push the refreshed lock"]["if"]
    assert "-- uv.lock .pre-commit-config.yaml" in steps["Push the refreshed lock"]["run"]
    assert "HAS_LOCK_TOKEN != 'true'" in steps["Ask for a lock refresh"]["if"]


def test_requirements_pins_match_the_lock() -> None:
    """A package pinned in requirements*.txt and locked in uv.lock has one version in both.

    pymdown-extensions and filelock drifted: the requirements kept 12.2 and 4.1.0 while
    the lock moved to 12.3 (and to filelock 4.2.0 on Python 3.11 and newer), because only
    constraints-ci.txt holds the lock.
    Packages the lock does not contain (audit and mutation tools) are not checked.
    """

    locked = _locked_versions()
    mismatched = [
        f"{path.name}: {name}=={version} (locked: {sorted(locked[_normalize(name)])})"
        for path in sorted(ROOT.glob("requirements*.txt"))
        for name, version in re.findall(
            r"(?m)^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==([^\s;#]+)",
            path.read_text(encoding="utf-8"),
        )
        if _normalize(name) in locked and version not in locked[_normalize(name)]
    ]

    assert mismatched == [], "pin the package in constraints-ci.txt and run `make lock`"
