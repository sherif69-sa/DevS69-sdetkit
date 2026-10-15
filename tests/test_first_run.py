"""The first run in a repository that is not a Python package, or has nothing to check yet.

`gate fast` read NO_SHIP in an empty `git init` repository and in a Go repository whose
`go test` passed. In both, doctor failed its high-severity pyproject check with
"pyproject.toml is missing" and advised "Fix pyproject.toml syntax." A repository without
pyproject.toml is not broken, and an empty one has nothing to prove: it reads NOT_RUN and
says what to add.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sdetkit import doctor
from sdetkit.gates import gate


def _pyproject_check(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    monkeypatch.chdir(root)
    rc = doctor.main(["--only", "pyproject", "--format", "json", "--no-workspace"])
    payload = json.loads(capsys.readouterr().out)
    return rc, payload["checks"]["pyproject"]


def test_a_repository_without_python_skips_the_pyproject_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "go.mod").write_text("module example.com/x\n\ngo 1.22\n", encoding="utf-8")

    rc, check = _pyproject_check(tmp_path, monkeypatch, capsys)

    assert rc == 0
    assert check["ok"] is True and check["skipped"] is True
    assert check["summary"] == "no pyproject.toml: not a Python package, nothing to check"
    assert check["fix"] == []


def test_a_setuptools_project_without_pyproject_passes_with_a_suggestion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n")

    rc, check = _pyproject_check(tmp_path, monkeypatch, capsys)

    assert rc == 0
    assert (check["ok"], check["severity"]) == (True, "low")
    assert check["summary"] == "no pyproject.toml; setup.py declares the project"
    assert check["fix"] == ["Consider adding pyproject.toml with [project] metadata (PEP 621)."]


def test_an_unparseable_pyproject_still_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")

    rc, check = _pyproject_check(tmp_path, monkeypatch, capsys)

    assert rc == 2
    assert (check["ok"], check["severity"]) == (False, "high")
    assert check["fix"] == ["Fix pyproject.toml syntax."]


def _git_repo(root: Path, files: dict[str, str]) -> Path:
    root.mkdir()
    for rel, text in files.items():
        (root / rel).write_text(text, encoding="utf-8")
    for args in (["init", "-q"], ["add", "-A"]):
        subprocess.run(["git", *args], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=root,
        check=True,
    )
    return root


def _gate_fast(root: Path, capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, dict]:
    rc = gate.main(["fast", "--root", str(root), "--format", "json", *args])
    return rc, json.loads(capsys.readouterr().out)


def test_an_empty_repository_reads_not_run_with_what_to_add(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _git_repo(tmp_path / "repo", {"README.md": "demo\n", ".gitignore": "build/\n"})
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)

    rc, payload = _gate_fast(repo, capsys, "--python", sys.executable)

    assert rc == 0
    assert payload["failed_steps"] == []  # doctor no longer fails on the missing pyproject
    assert [step["id"] for step in payload["steps"]] == ["doctor"]
    verdict = payload["verdict"]
    assert verdict["decision"] == "NOT_RUN"
    assert verdict["reasons"] == [
        "nothing in this repository was checked: no tests, and no ruff or mypy configuration"
    ]
    assert verdict["next_action"].startswith("Add tests (tests/ or pytest configuration)")
    assert "**Next:** `Add tests" in gate._format_md(payload)


def test_a_repository_with_a_detected_suite_is_not_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Go suite the caller left out on purpose is not "nothing to check"."""

    repo = _git_repo(
        tmp_path / "repo",
        {"go.mod": "module example.com/x\n\ngo 1.22\n", "x_test.go": "package x\n"},
    )

    rc, payload = _gate_fast(repo, capsys, "--no-tests", "--no-doctor")

    assert rc == 0
    assert payload["verdict"]["decision"] == "SHIP"
