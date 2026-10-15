from __future__ import annotations

from pathlib import Path

import pytest

from sdetkit.gates import gate_config as gc


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_invalid_pyproject_is_treated_as_unconfigured(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", "not = [valid toml\n")
    config = gc.load_gate_config(tmp_path)
    assert config == gc.GateConfig()
    assert gc.ruff_configured(tmp_path) is False


def test_ci_templates_must_be_boolean(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", '[tool.sdetkit.gate]\nci_templates = "yes"\n')
    config = gc.load_gate_config(tmp_path)
    assert config.ci_templates is False
    assert config.errors == ("[tool.sdetkit.gate] ci_templates must be a boolean",)


@pytest.mark.parametrize(
    ("relative", "text"),
    [
        ("tests/test_a.py", ""),
        ("test/test_a.py", ""),
        ("conftest.py", ""),
        ("pytest.ini", "[pytest]\n"),
        ("pyproject.toml", "[tool.pytest.ini_options]\naddopts = '-q'\n"),
        ("setup.cfg", "[tool:pytest]\naddopts = -q\n"),
        ("tox.ini", "[pytest]\naddopts = -q\n"),
        ("test_root.py", ""),
        ("root_test.py", ""),
    ],
)
def test_has_tests_detects_common_layouts(tmp_path: Path, relative: str, text: str) -> None:
    assert gc.has_tests(tmp_path) is False
    _write(tmp_path / relative, text)
    assert gc.has_tests(tmp_path) is True


def test_unreadable_ini_does_not_count_as_pytest_config(tmp_path: Path) -> None:
    _write(tmp_path / "setup.cfg", "this is [not an ini\n")
    assert gc.has_tests(tmp_path) is False


@pytest.mark.parametrize(
    ("relative", "text"),
    [
        ("ruff.toml", "line-length = 100\n"),
        (".ruff.toml", "line-length = 100\n"),
        ("pyproject.toml", "[tool.ruff]\nline-length = 100\n"),
        (
            ".pre-commit-config.yaml",
            "repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n",
        ),
    ],
)
def test_ruff_configured_detects_config_sources(tmp_path: Path, relative: str, text: str) -> None:
    assert gc.ruff_configured(tmp_path) is False
    _write(tmp_path / relative, text)
    assert gc.ruff_configured(tmp_path) is True


def test_pre_commit_without_ruff_is_not_ruff_config(tmp_path: Path) -> None:
    _write(tmp_path / ".pre-commit-config.yaml", "repos: []\n")
    assert gc.ruff_configured(tmp_path) is False


@pytest.mark.parametrize(
    ("relative", "text", "expected"),
    [
        ("pyproject.toml", "[tool.mypy]\nfiles = ['pkg']\n", ()),
        ("pyproject.toml", "[tool.mypy]\nstrict = true\n", (".",)),
        (".mypy.ini", "[mypy]\nstrict = True\n", (".",)),
        ("setup.cfg", "[mypy]\nfiles = pkg\n", ()),
    ],
)
def test_plan_mypy_follows_repository_config(
    tmp_path: Path, relative: str, text: str, expected: tuple[str, ...]
) -> None:
    _write(tmp_path / relative, text)
    plan = gc.plan_mypy(tmp_path, gc.load_gate_config(tmp_path), None)
    assert plan.skipped is False
    assert plan.args == expected


def test_plan_mypy_targets_src_when_present(tmp_path: Path) -> None:
    _write(tmp_path / "mypy.ini", "[mypy]\n")
    (tmp_path / "src").mkdir()
    plan = gc.plan_mypy(tmp_path, gc.GateConfig(), None)
    assert plan.args == ("src",)


def test_plan_mypy_cli_args_and_config_win(tmp_path: Path) -> None:
    config = gc.GateConfig(mypy_args=("pkg",))
    assert gc.plan_mypy(tmp_path, config, "a b").args == ("a", "b")
    assert gc.plan_mypy(tmp_path, config, None).args == ("pkg",)


def test_plan_ruff_uses_configured_paths(tmp_path: Path) -> None:
    plan = gc.plan_ruff(tmp_path, gc.GateConfig(ruff_paths=("lib",)))
    assert plan.args == ("lib",)


def test_plan_pytest_full_suite_overrides_config(tmp_path: Path) -> None:
    config = gc.GateConfig(pytest_args=("-q", "tests/smoke"))
    assert gc.plan_pytest(tmp_path, config, None, True).args == ("-q",)
