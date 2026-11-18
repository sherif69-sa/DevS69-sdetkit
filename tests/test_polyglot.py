from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from sdetkit import cli, test_bootstrap


def test_discover_polyglot_projects(tmp_path: Path) -> None:
    # Python project
    py_dir = tmp_path / "services" / "py-app"
    py_dir.mkdir(parents=True)
    (py_dir / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    (py_dir / "tests").mkdir()
    (py_dir / "tests" / "test_app.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    # Go project
    go_dir = tmp_path / "services" / "go-app"
    go_dir.mkdir(parents=True)
    (go_dir / "go.mod").write_text("module example.com/goapp\n", encoding="utf-8")

    # JS project
    js_dir = tmp_path / "frontend"
    js_dir.mkdir(parents=True)
    (js_dir / "package.json").write_text('{"scripts": {"test": "vitest"}}\n', encoding="utf-8")

    # Java project
    java_dir = tmp_path / "backend-java"
    java_dir.mkdir(parents=True)
    (java_dir / "pom.xml").write_text("<project></project>\n", encoding="utf-8")

    with (
        patch("sdetkit.js_tests.detect_runner", return_value="vitest"),
        patch("sdetkit.java_tests.detect_java_runner", return_value="maven"),
    ):
        projects = test_bootstrap.discover_polyglot_projects(tmp_path)

    folders = {p["folder"] for p in projects}
    assert "services/py-app" in folders
    assert "services/go-app" in folders
    assert "frontend" in folders
    assert "backend-java" in folders

    by_folder = {p["folder"]: p for p in projects}
    assert by_folder["services/py-app"]["language"] == "python"
    assert by_folder["services/py-app"]["runner"] == "pytest"
    assert by_folder["services/go-app"]["language"] == "go"
    assert by_folder["services/go-app"]["runner"] == "go"
    assert by_folder["frontend"]["language"] == "javascript"
    assert by_folder["frontend"]["runner"] == "vitest"
    assert by_folder["backend-java"]["language"] == "java"
    assert by_folder["backend-java"]["runner"] == "maven"


def test_render_polyglot_markdown() -> None:
    report = {
        "verdict": "PASS",
        "totals": {
            "projects": 2,
            "passed": 42,
            "failed": 0,
            "skipped": 1,
            "total": 43,
        },
        "matrix": [
            {
                "folder": "backend",
                "language": "python",
                "runner": "pytest",
                "passed": 40,
                "failed": 0,
                "skipped": 1,
                "total": 41,
                "duration_seconds": 1.25,
                "status": "PASSED",
                "output_tail": "",
            },
            {
                "folder": "frontend",
                "language": "javascript",
                "runner": "vitest",
                "passed": 2,
                "failed": 0,
                "skipped": 0,
                "total": 2,
                "duration_seconds": 0.45,
                "status": "PASSED",
                "output_tail": "",
            },
        ],
    }
    md = test_bootstrap.render_polyglot_markdown(report)
    assert "# SDETKit Polyglot Test Matrix Radar" in md
    assert "**Verdict:** `PASS`" in md
    assert "| `backend` | python | `pytest` | 40 | 0 | 1 | 41 | 1.25s | **PASSED** |" in md
    assert "| `frontend` | javascript | `vitest` | 2 | 0 | 0 | 2 | 0.45s | **PASSED** |" in md


def test_render_polyglot_markdown_with_failures() -> None:
    report = {
        "verdict": "FAIL",
        "totals": {
            "projects": 1,
            "passed": 0,
            "failed": 1,
            "skipped": 0,
            "total": 1,
        },
        "matrix": [
            {
                "folder": "pkg/api",
                "language": "go",
                "runner": "go",
                "passed": 0,
                "failed": 1,
                "skipped": 0,
                "total": 1,
                "duration_seconds": 0.88,
                "status": "FAILED",
                "output_tail": "FAIL: TestEndpoint (0.01s)\n  assertion error at api_test.go:42",
            }
        ],
    }
    md = test_bootstrap.render_polyglot_markdown(report)
    assert "**Verdict:** `FAIL`" in md
    assert "### Project Diagnostics" in md
    assert "FAIL: TestEndpoint" in md


def test_run_polyglot_matrix_no_projects(tmp_path: Path) -> None:
    report = test_bootstrap.run_polyglot_matrix(tmp_path)
    assert report["schema_version"] == "sdetkit.polyglot_matrix.v1"
    assert report["verdict"] == "NO_TESTS"
    assert report["totals"]["projects"] == 0


def test_run_polyglot_matrix_mock_execution(tmp_path: Path) -> None:
    py_dir = tmp_path / "app"
    py_dir.mkdir()
    (py_dir / "pyproject.toml").write_text("[project]\nname='app'\n", encoding="utf-8")
    (py_dir / "tests").mkdir()

    with patch("sdetkit.test_bootstrap._run_python_project") as mock_run:
        mock_run.return_value = {
            "exit_code": 0,
            "duration_seconds": 0.5,
            "counts": {"passed": 5, "failed": 0, "skipped": 0, "total": 5},
            "output_tail": "5 passed in 0.5s",
            "runner_missing": False,
            "timed_out": False,
        }
        report = test_bootstrap.run_polyglot_matrix(tmp_path)

    assert report["verdict"] == "PASS"
    assert report["totals"]["passed"] == 5
    assert len(report["matrix"]) == 1
    assert report["matrix"][0]["status"] == "PASSED"


def test_polyglot_cli_main(tmp_path: Path, capsys) -> None:
    json_out = tmp_path / "matrix.json"
    sum_out = tmp_path / "matrix.md"

    code = test_bootstrap.polyglot_main(
        [
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--out",
            str(json_out),
            "--summary-out",
            str(sum_out),
        ]
    )
    assert code == 0
    assert json_out.is_file()
    assert sum_out.is_file()

    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["schema_version"] == "sdetkit.polyglot_matrix.v1"
    assert data["verdict"] == "NO_TESTS"


def test_polyglot_cli_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def _fake_run(module_name: str, args: list[str]) -> int:
        calls.append((module_name, list(args)))
        return 0

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)

    rc = cli.main(["polyglot", "--format", "json"])
    assert rc == 0
    assert calls == [("sdetkit.test_bootstrap", ["polyglot", "--format", "json"])]

    calls.clear()
    rc_verify = cli.main(["verify", "polyglot", "--languages", "python"])
    assert rc_verify == 0
    assert calls == [("sdetkit.test_bootstrap", ["--languages", "python"])]
