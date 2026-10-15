"""`gate fast` runs mypy and ruff the way the repository itself runs them.

The external repository proof found two invented commands: python-attrs/attrs configures
mypy without `files` and type-checks only its `.pyi` stubs from tox, but the gate ran
`mypy src`; psf/requests excludes `tests/test_lowlevel.py` from its pre-commit
`ruff-format` hook, but the gate checked it anyway. It also suggested a pip setup without
`requirements-dev.txt`, so requests' environment had no pytest.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from sdetkit import gate
from sdetkit.gates.gate_config import GateConfig, plan_mypy, plan_ruff
from sdetkit.gates.project_env import setup_command
from sdetkit.gates.repo_commands import pre_commit_files, pre_commit_hook, tox_mypy_commands

PRE_COMMIT = """\
exclude: 'docs/|ext/'
repos:
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.16.4
  hooks:
    - id: ruff-check
      args: [--fix]
    - id: ruff-format
      exclude: tests/test_lowlevel.py
- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v2.4.0
  hooks:
    - id: mypy
      files: ^(src/|testing/)
      args: []
"""

TOX = """\
[tox]
env_list = py, 3.1{0-5}-mypy

[testenv]
commands =
    tests: pytest {posargs:-n auto}
    mypy: mypy typing_tests
    mypy: python -m mypy src/pkg/__init__.pyi {posargs}
    mypy: mypy typing_tests
    lint: mypy
"""


def _git_repo(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


@pytest.fixture
def requests_like(tmp_path: Path) -> Path:
    return _git_repo(
        tmp_path,
        {
            ".pre-commit-config.yaml": PRE_COMMIT,
            "pyproject.toml": '[project]\nname = "pkg"\n\n[tool.ruff]\n\n[tool.mypy]\nstrict = true\n',
            "setup.py": "",
            "src/pkg/__init__.py": "",
            "testing/test_a.py": "",
            "tests/test_lowlevel.py": "",
            "tests/test_main.py": "",
            "docs/conf.py": "",
            "README.md": "",
        },
    )


@needs_git
def test_pre_commit_selects_files_like_pre_commit(requests_like: Path) -> None:
    fmt = pre_commit_hook(requests_like, {"ruff-format"})
    mypy = pre_commit_hook(requests_like, {"mypy"})
    assert fmt is not None and mypy is not None

    assert pre_commit_files(requests_like, fmt) == (
        "setup.py",
        "src/pkg/__init__.py",
        "testing/test_a.py",
        "tests/test_main.py",
    )
    assert pre_commit_files(requests_like, mypy) == ("src/pkg/__init__.py", "testing/test_a.py")


@needs_git
def test_ruff_honours_each_hooks_exclusions(requests_like: Path) -> None:
    check = plan_ruff(requests_like, GateConfig(), command="check")
    fmt = plan_ruff(requests_like, GateConfig(), command="format")

    assert fmt.source == "pre-commit ruff-format hook"
    assert fmt.args[0] == "--force-exclude"
    assert "tests/test_lowlevel.py" not in fmt.args
    assert "tests/test_lowlevel.py" in check.args  # only the format hook excludes it
    assert "docs/conf.py" not in check.args  # the top-level exclude applies to both
    # An explicit [tool.sdetkit.gate] ruff_paths still wins.
    assert plan_ruff(requests_like, GateConfig(ruff_paths=("src",))).args == ("src",)


def test_ruff_without_narrowing_hooks_keeps_the_default_paths(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n- repo: r\n  hooks:\n  - id: ruff-format\n", encoding="utf-8"
    )

    assert plan_ruff(tmp_path, GateConfig(), command="format").args == ("src",)


@needs_git
def test_mypy_without_files_follows_the_pre_commit_hook(requests_like: Path) -> None:
    plan = plan_mypy(requests_like, GateConfig(), None)

    assert plan.source == "pre-commit mypy hook"
    assert plan.args == ("src/pkg/__init__.py", "testing/test_a.py")


def test_mypy_without_files_follows_tox(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n", encoding="utf-8")
    (tmp_path / "tox.ini").write_text(TOX, encoding="utf-8")
    (tmp_path / "src").mkdir()

    plan = plan_mypy(tmp_path, GateConfig(), None)

    assert tox_mypy_commands(tmp_path) == [
        ("typing_tests",),
        ("src/pkg/__init__.pyi",),
        (),
    ]
    assert (plan.source, plan.args, plan.more) == (
        "tox.ini",
        ("typing_tests",),
        (("src/pkg/__init__.pyi",),),
    )


def test_mypy_files_and_explicit_args_still_win(tmp_path: Path) -> None:
    (tmp_path / "tox.ini").write_text(TOX, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "pyproject.toml").write_text('[tool.mypy]\nfiles = ["src"]\n', encoding="utf-8")

    assert plan_mypy(tmp_path, GateConfig(), None).args == ()
    assert plan_mypy(tmp_path, GateConfig(mypy_args=("pkg",)), None).args == ("pkg",)

    (tmp_path / "pyproject.toml").write_text("[tool.mypy]\n", encoding="utf-8")
    (tmp_path / "tox.ini").unlink()
    assert plan_mypy(tmp_path, GateConfig(), None).args == ("src",)


def test_the_gate_runs_every_tox_mypy_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.mypy]\n", encoding="utf-8")
    (tmp_path / "tox.ini").write_text(TOX, encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, Any]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)

    rc = gate.main(["fast", "--root", str(tmp_path), "--format", "json", "--only", "mypy"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert [cmd[3:] for cmd in calls] == [["typing_tests"], ["src/pkg/__init__.pyi"]]
    assert payload["steps"][0]["targets_from"] == "tox.ini"


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (
            {"setup.py": "", "requirements-dev.txt": ""},
            "python -m venv .venv && .venv/bin/python -m pip install -e . -r requirements-dev.txt",
        ),
        (
            {
                "pyproject.toml": "[project.optional-dependencies]\ntests = []\ndocs = []\n",
            },
            "python -m venv .venv && .venv/bin/python -m pip install -e .[tests]",
        ),
        (
            {"requirements.txt": "", "requirements/test.txt": ""},
            "python -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
            " -r requirements/test.txt",
        ),
    ],
)
def test_pip_setup_installs_the_test_dependencies(
    tmp_path: Path, files: dict[str, str], expected: str
) -> None:
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")

    assert setup_command(tmp_path) == expected


TRICKY = """\
# leading comment
default_language_version:
  python: python3
files: '^(src|tests)/'   # only these
exclude: |
  (?x)^(
    tests/fixtures/.*|
    src/pkg/_vendor/.*
  )$
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: "v0.16.4"
    hooks:
      - id: ruff
        args: [--fix, "--exit-non-zero-on-fix", '--ignore-words-list=inout,te']
        exclude: "^tests/data/.*\\\\.py$"
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v2.4.0
    hooks:
      - name: types
        id: mypy
        args:
          - --strict
          - '--python-version=3.12'
        additional_dependencies:
          - types-requests
        files: ^src/
  - repo: local
    hooks:
    -   id: rst
        name: rst ok # not a comment inside: '#'
        entry: rst-lint
        files: ^(HOWTORELEASE.rst|README.rst)$
"""


def _yaml_view(text: str) -> dict[str, Any]:
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load(text)
    view: dict[str, Any] = {key: data[key] for key in ("files", "exclude") if key in data}
    view["hooks"] = [
        {
            key: str(hook[key]).lower() if key == "pass_filenames" else hook[key]
            for key in ("id", "files", "exclude", "args", "pass_filenames")
            if key in hook
        }
        for repo in data.get("repos") or []
        for hook in repo.get("hooks") or []
    ]
    return view


@pytest.mark.parametrize(
    "text",
    [
        TRICKY,
        PRE_COMMIT,
        (Path(__file__).resolve().parents[1] / ".pre-commit-config.yaml").read_text(
            encoding="utf-8"
        ),
    ],
    ids=["tricky", "requests-like", "this-repository"],
)
def test_the_pre_commit_reader_agrees_with_pyyaml(text: str) -> None:
    from sdetkit.gates.repo_commands import read_pre_commit

    expected = _yaml_view(text)
    got = read_pre_commit(text)
    # Block scalars keep their line breaks in YAML; the reader trims each line's indent.
    if isinstance(expected.get("exclude"), str):
        expected["exclude"] = "\n".join(line.strip() for line in expected["exclude"].splitlines())
        got["exclude"] = "\n".join(line.strip() for line in str(got.get("exclude")).splitlines())

    assert got == expected


def test_a_hook_that_takes_no_filenames_runs_its_arguments_as_is(tmp_path: Path) -> None:
    """This repository's own hook: `args: [src]` with `pass_filenames: false` is `mypy src`.

    Appending the selected files as well made mypy fail with "Duplicate module named
    'sdetkit'" during release qualification.
    """

    (tmp_path / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n[tool.ruff]\n")
    (tmp_path / "src/pkg").mkdir(parents=True)
    (tmp_path / "src/pkg/__init__.py").write_text("")
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "exclude: ^docs/\n"
        "repos:\n"
        "  - repo: https://github.com/pre-commit/mirrors-mypy\n"
        "    hooks:\n"
        "      - id: mypy\n"
        "        args: [src]\n"
        "        pass_filenames: false\n"
        "        files: ^src/\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: ruff-format\n"
        "        pass_filenames: false\n"
    )

    mypy = plan_mypy(tmp_path, GateConfig(), None)
    fmt = plan_ruff(tmp_path, GateConfig(), command="format")

    assert (mypy.args, mypy.source) == (("src",), "pre-commit mypy hook")
    assert (fmt.args, fmt.source) == (("src",), "")
