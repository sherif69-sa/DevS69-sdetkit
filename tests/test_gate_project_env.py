"""`gate fast` runs a repository's checks in the project's own environment.

On fresh clones of pallets/itsdangerous and pallets/markupsafe, `gate fast` returned
NO_SHIP for code that was fine: pytest ran with SDETKit's interpreter, where the
src-layout project was not installed ("No module named 'itsdangerous'"), and mypy read
numpy stubs from that interpreter's site-packages. Now the gate uses the repository's
`.venv` when there is one, and reports a failure that comes from the environment as
NOT_RUN with the command that sets it up.
"""

from __future__ import annotations

import json
import os
import site
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from sdetkit import gate
from sdetkit.gates import project_env
from sdetkit.gates.project_env import (
    SDETKIT_SOURCE,
    ProjectPython,
    mypy_environment_problem,
    own_import_names,
    pytest_environment_problem,
    resolve_project_python,
    setup_command,
)

NO_ENV: dict[str, str] = {}


def _src_layout_repo(root: Path) -> Path:
    (root / "src/demo").mkdir(parents=True)
    (root / "src/demo/__init__.py").write_text("def add(a, b):\n    return a + b\n")
    (root / "tests").mkdir()
    (root / "tests/test_demo.py").write_text(
        "from demo import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n\n[tool.pytest.ini_options]\n'
        'testpaths = ["tests"]\n'
    )
    (root / "uv.lock").write_text("version = 1\n")
    return root


def _venv(root: Path, *, with_project: bool) -> Path:
    """A real .venv that can run pytest (via this interpreter's site dirs), optionally with
    the project installed the way `pip install -e .` would."""

    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(root / ".venv")],
        check=True,
        capture_output=True,
    )
    python = project_env.venv_python(root / ".venv")
    assert python is not None
    out = subprocess.run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True,
        capture_output=True,
        text=True,
    )
    purelib = Path(out.stdout.strip())
    purelib.mkdir(parents=True, exist_ok=True)
    dirs = [p for p in sys.path if p.endswith(("site-packages", "dist-packages"))]
    dirs += [site.getusersitepackages()]
    (purelib / "host.pth").write_text("\n".join(dirs) + "\n")
    if with_project:
        (purelib / "demo.pth").write_text(str(root / "src") + "\n")
    return python


def _gate(root: Path, *args: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any]]:
    rc = gate.main(["fast", "--root", str(root), "--format", "json", "--only", *args])
    return rc, json.loads(capsys.readouterr().out)


@pytest.fixture(autouse=True)
def _no_active_virtualenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)


def test_an_uninstalled_project_is_not_run_not_no_ship(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, payload = _gate(_src_layout_repo(tmp_path), "pytest", capsys=capsys)

    assert rc == 2
    assert payload["environment"]["source"] == SDETKIT_SOURCE
    card = payload["next_action"]
    assert card["classification"] == "environment"
    assert "own package 'demo'" in card["first_failure"]
    assert card["next_command"] == "uv sync && python -m sdetkit gate fast"
    assert payload["verdict"]["decision"] == "NOT_RUN"
    assert payload["verdict"]["reasons"][0].startswith("pytest did not run against this repository")


def test_the_repositorys_venv_runs_the_tests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _src_layout_repo(tmp_path)
    python = _venv(root, with_project=True)

    rc, payload = _gate(root, "pytest", capsys=capsys)

    assert rc == 0, payload["steps"]
    assert payload["environment"] == {"python": str(python), "source": ".venv"}
    assert payload["steps"][0]["cmd"][:3] == [str(python), "-m", "pytest"]
    assert payload["verdict"]["decision"] == "SHIP"


def test_a_venv_without_pytest_is_not_run(tmp_path: Path) -> None:
    root = _src_layout_repo(tmp_path)
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(root / ".venv")],
        check=True,
        capture_output=True,
    )

    rc = gate.main(["fast", "--root", str(root), "--format", "json", "--only", "pytest"])

    payload = json.loads((root / ".sdetkit/runs/gate-latest.json").read_text())
    assert rc == 2
    [step] = payload["steps"]
    assert step["rc"] is None
    assert step["environment_problem"].startswith("pytest is not installed in the project")
    assert payload["verdict"]["decision"] == "NOT_RUN"


def test_explicit_python_wins_and_must_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _src_layout_repo(tmp_path)
    missing = str(tmp_path / "nope/python")

    rc = gate.main(["fast", "--root", str(root), "--python", missing, "--only", "pytest"])

    assert rc == 2
    assert f"--python {missing} did not run" in capsys.readouterr().err


def test_a_broken_venv_falls_back_with_a_note(tmp_path: Path) -> None:
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").write_text("not an interpreter")

    env = resolve_project_python(tmp_path, environ=NO_ENV)

    assert env.source == SDETKIT_SOURCE and env.executable == sys.executable
    assert env.note.startswith("ignored .venv (")


@pytest.mark.skipif(sys.platform == "win32", reason="uses a shell-script stand-in for poetry")
def test_poetrys_environment_outside_the_repository_is_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "poetry.lock").write_text("")
    python = _venv(tmp_path / "cache", with_project=False)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "poetry").write_text(f"#!/bin/sh\necho {python}\n")
    (bin_dir / "poetry").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    env = resolve_project_python(repo, environ=NO_ENV)

    assert (env.executable, env.source) == (str(python), "poetry")
    assert "pytest" in env.tools


def test_the_interpreter_sdetkit_runs_in_is_used_directly(tmp_path: Path) -> None:
    if project_env.venv_python(Path(sys.prefix)) is None:
        pytest.skip("this interpreter's prefix has no bin/python")

    env = resolve_project_python(tmp_path, environ={"VIRTUAL_ENV": sys.prefix})

    assert env == ProjectPython(sys.executable, "VIRTUAL_ENV", frozenset(project_env.TOOLS))


def test_sdetkits_mypy_reads_the_projects_packages() -> None:
    without = ProjectPython("/p/.venv/bin/python", ".venv", frozenset({"pytest"}))
    with_mypy = ProjectPython("/p/.venv/bin/python", ".venv", frozenset({"mypy"}))

    assert gate._mypy_command(without, ("src",)) == [
        sys.executable,
        "-m",
        "mypy",
        "src",
        "--python-executable=/p/.venv/bin/python",
    ]
    assert gate._mypy_command(with_mypy, ("src",)) == ["/p/.venv/bin/python", "-m", "mypy", "src"]
    assert without.runner("ruff") == [sys.executable, "-m", "ruff"]


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"uv.lock": ""}, "uv sync"),
        ({"poetry.lock": ""}, "poetry install"),
        ({"pdm.lock": ""}, "pdm install"),
        ({"Pipfile.lock": "{}"}, "pipenv install --dev"),
        ({"pyproject.toml": ""}, "python -m venv .venv && .venv/bin/python -m pip install -e ."),
        (
            {"requirements.txt": ""},
            "python -m venv .venv && .venv/bin/python -m pip install -r requirements.txt",
        ),
        ({}, "python -m venv .venv"),
    ],
)
def test_setup_command_follows_the_lockfile(
    tmp_path: Path, files: dict[str, str], expected: str
) -> None:
    for name, text in files.items():
        (tmp_path / name).write_text(text)

    assert setup_command(tmp_path) == expected


def test_which_missing_modules_are_the_environment(tmp_path: Path) -> None:
    _src_layout_repo(tmp_path)
    (tmp_path / "flat").mkdir()
    (tmp_path / "flat/__init__.py").write_text("")
    sdetkit_env = ProjectPython(sys.executable, SDETKIT_SOURCE)
    venv = ProjectPython("/p/.venv/bin/python", ".venv", frozenset({"pytest"}))

    assert own_import_names(tmp_path) == {"demo", "flat"}

    def problem(module: str, env: ProjectPython) -> str | None:
        output = f"E   ModuleNotFoundError: No module named '{module}'\n"
        return pytest_environment_problem(output, tmp_path, env)

    assert problem("demo._speedups", venv) is not None
    assert problem("requests", sdetkit_env) is not None
    # In the project's own environment a missing dependency may be a real undeclared one.
    assert problem("requests", venv) is None
    # A missing tool keeps its own install recommendation.
    assert problem("pytest", sdetkit_env) is None
    assert pytest_environment_problem("1 failed, 3 passed\n", tmp_path, sdetkit_env) is None


def test_mypy_errors_only_in_installed_packages_are_the_environment(tmp_path: Path) -> None:
    numpy = "/usr/lib/python3/dist-packages/numpy/__init__.pyi:737: error: Type statement\n"
    venv_stub = ".venv/lib/python3.13/site-packages/x/__init__.pyi:1: error: bad [syntax]\n"
    ours = "src/demo/__init__.py:3: error: Incompatible return value [return-value]\n"

    assert "numpy/__init__.pyi" in (mypy_environment_problem(numpy, tmp_path) or "")
    assert mypy_environment_problem(venv_stub, tmp_path) is not None
    assert mypy_environment_problem(ours, tmp_path) is None
    assert mypy_environment_problem(numpy + ours, tmp_path) is None
    assert mypy_environment_problem("Success: no issues found\n", tmp_path) is None


def test_a_code_failure_outranks_an_environment_problem(tmp_path: Path) -> None:
    payload: dict[str, Any] = {
        "profile": "fast",
        "ok": False,
        "failed_steps": ["mypy", "pytest"],
        "steps": [
            {
                "id": "mypy",
                "ok": False,
                "stdout": "",
                "stderr": "",
                "environment_problem": "mypy read numpy",
                "next_command": "uv sync && python -m sdetkit gate fast",
            },
            {"id": "pytest", "ok": False, "stdout": "FAILED tests/test_a.py::test_x", "stderr": ""},
        ],
    }

    gate._attach_next_action(payload)
    gate._attach_verdict(payload, source="gate fast", root=tmp_path)

    assert payload["next_action"]["classification"] != "environment"
    assert payload["verdict"]["decision"] == "NO_SHIP"


def test_stable_json_leaves_out_the_machine_specific_environment() -> None:
    payload = {"root": "/r", "steps": [], "environment": {"python": "/r/.venv/bin/python"}}

    assert "environment" not in gate._normalize_gate_payload(payload)
