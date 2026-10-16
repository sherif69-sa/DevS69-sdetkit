"""Other repositories can run `gate fast` as a pre-commit hook.

`.pre-commit-hooks.yaml` declares the `sdetkit-gate` hook. pre-commit installs SDETKit in
an environment of its own and points VIRTUAL_ENV at it, so the gate looks past that
environment for the developer's interpreter (see `sdetkit.gates.project_env`).

The end-to-end tests run `pre-commit try-repo` against this checkout, which installs it
from source; they need the network and run in CI's "Pre-commit hook (self)" job.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pre_commit_clientlib = pytest.importorskip("pre_commit.clientlib")

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".pre-commit-hooks.yaml"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def test_the_manifest_is_valid_and_runs_the_fast_gate_once_per_push() -> None:
    [hook] = pre_commit_clientlib.load_manifest(str(MANIFEST))

    assert hook["id"] == "sdetkit-gate"
    assert hook["entry"] == "sdetkit gate fast"
    assert hook["language"] == "python"
    # The gate checks the whole repository, once, whatever files changed.
    assert hook["pass_filenames"] is False
    assert hook["always_run"] is True
    assert hook["stages"] == ["pre-push", "manual"]


def test_the_hook_entry_is_an_installed_console_script() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'sdetkit = "sdetkit.cli:main"' in pyproject


def _project(root: Path, *, passing: bool) -> Path:
    (root / "src/app").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "app"\nversion = "0.1.0"\n\n'
        '[tool.setuptools.packages.find]\nwhere = ["src"]\n'
    )
    (root / "src/app/__init__.py").write_text("def add(a, b):\n    return a + b\n")
    expected = 3 if passing else 4
    (root / "tests/test_add.py").write_text(
        f"from app import add\n\n\ndef test_add():\n    assert add(1, 2) == {expected}\n"
    )
    (root / ".gitignore").write_text(".venv/\n.sdetkit/\nbuild/\n")
    return root


def _venv_with_project(root: Path) -> None:
    subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True)
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [str(python), "-m", "pip", "install", "-q", "pytest", "-e", str(root)], check=True
    )


def _try_repo(project: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **GIT_ENV}
    env.pop("VIRTUAL_ENV", None)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=project, check=True, env=env)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pre_commit",
            "try-repo",
            str(ROOT),
            "sdetkit-gate",
            "--all-files",
            "--hook-stage",
            "pre-push",
            "--verbose",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        env=env,
        timeout=900,
    )


@pytest.mark.network
@pytest.mark.parametrize(
    ("passing", "outcome", "verdict"),
    [(True, "Passed", "decision: CONTINUE"), (False, "Failed", "decision: NO-SHIP")],
)
def test_the_hook_runs_the_projects_tests_in_its_venv(
    tmp_path: Path, passing: bool, outcome: str, verdict: str
) -> None:
    project = _project(tmp_path / "app", passing=passing)
    _venv_with_project(project)

    proc = _try_repo(project)

    out = proc.stdout + proc.stderr
    assert f"sdetkit gate fast{'.' * 10}" in out and outcome in out, out
    assert "(.venv)" in out, out
    assert verdict in out, out


@pytest.mark.network
def test_without_a_project_environment_the_hook_says_not_run(tmp_path: Path) -> None:
    project = _project(tmp_path / "app", passing=True)

    proc = _try_repo(project)

    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    # Not pre-commit's own environment, and not a test failure.
    assert "(VIRTUAL_ENV)" not in out, out
    assert "decision: NOT_RUN" in out and "classification: environment" in out, out
