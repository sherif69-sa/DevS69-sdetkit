from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from sdetkit import dependency_map as test_impact


@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    src = tmp_path / "src" / "sample"
    src.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir(parents=True)

    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "core.py").write_text("def core_fn(): return 42\n", encoding="utf-8")
    (src / "service.py").write_text(
        "from sample.core import core_fn\ndef run(): return core_fn() * 2\n",
        encoding="utf-8",
    )
    (src / "util.py").write_text("def helper(): return 'ok'\n", encoding="utf-8")

    (tests / "test_core.py").write_text(
        "from sample.core import core_fn\ndef test_c(): assert core_fn() == 42\n",
        encoding="utf-8",
    )
    (tests / "test_service.py").write_text(
        "from sample.service import run\ndef test_s(): assert run() == 84\n",
        encoding="utf-8",
    )
    (tests / "test_unrelated.py").write_text(
        "def test_u(): assert 1 == 1\n",
        encoding="utf-8",
    )

    return tmp_path


def test_build_import_graph(mini_repo: Path) -> None:
    graph = test_impact.build_import_graph(mini_repo)

    assert "src/sample/core.py" in graph.source_files
    assert "src/sample/service.py" in graph.source_files
    assert "tests/test_core.py" in graph.test_files
    assert "tests/test_service.py" in graph.test_files
    assert "tests/test_unrelated.py" in graph.test_files

    # service imports core
    assert "src/sample/core.py" in graph.forward_graph["src/sample/service.py"]
    assert "src/sample/service.py" in graph.reverse_graph["src/sample/core.py"]

    # test_core imports core
    assert "src/sample/core.py" in graph.forward_graph["tests/test_core.py"]
    assert "tests/test_core.py" in graph.reverse_graph["src/sample/core.py"]


def test_analyze_impact_direct_and_transitive(mini_repo: Path) -> None:
    report = test_impact.analyze_impact(
        mini_repo,
        files=["src/sample/core.py"],
    )

    assert report["clean"] is False
    assert report["global_config_changed"] is False
    assert "tests/test_core.py" in report["directly_impacted_tests"]
    assert "tests/test_service.py" in report["transitively_impacted_tests"]
    assert "tests/test_unrelated.py" not in report["all_impacted_tests"]
    assert report["selected_tests_count"] == 2
    assert report["total_tests_count"] == 3
    assert report["reduction_pct"] == 33.33
    assert "pytest" in report["recommended_pytest_command"]


def test_analyze_impact_service_only(mini_repo: Path) -> None:
    report = test_impact.analyze_impact(
        mini_repo,
        files=["src/sample/service.py"],
    )

    assert "tests/test_service.py" in report["directly_impacted_tests"]
    assert "tests/test_core.py" not in report["all_impacted_tests"]
    assert "tests/test_unrelated.py" not in report["all_impacted_tests"]
    assert report["selected_tests_count"] == 1


def test_analyze_impact_test_file_itself(mini_repo: Path) -> None:
    report = test_impact.analyze_impact(
        mini_repo,
        files=["tests/test_core.py"],
    )

    assert "tests/test_core.py" in report["directly_impacted_tests"]
    assert report["selected_tests_count"] == 1


def test_analyze_impact_global_config_triggers_all(mini_repo: Path) -> None:
    report = test_impact.analyze_impact(
        mini_repo,
        files=["pyproject.toml"],
    )

    assert report["global_config_changed"] is True
    assert report["selected_tests_count"] == 3
    assert report["reduction_pct"] == 0.0
    assert "Global build/test configuration modified" in report["reason"]


def test_analyze_impact_clean_tree(mini_repo: Path) -> None:
    report = test_impact.analyze_impact(
        mini_repo,
        files=[],
    )

    assert report["clean"] is True
    assert report["selected_tests_count"] == 0
    assert report["reduction_pct"] == 100.0


def test_run_impacted_tests_empty() -> None:
    empty_report = {"all_impacted_tests": []}
    res = test_impact.run_impacted_tests(empty_report, root=Path("."))
    assert res["ok"] is True
    assert res["executed"] is False
    assert res["selected_tests_count"] == 0


def test_run_impacted_tests_execution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["pytest"], 0, stdout="1 passed", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = {"all_impacted_tests": ["tests/test_one.py"]}
    res = test_impact.run_impacted_tests(report, root=tmp_path)
    assert res["ok"] is True
    assert res["executed"] is True
    assert res["returncode"] == 0


def test_render_markdown_clean_and_impacted() -> None:
    clean_report = {"clean": True}
    assert "CLEAN" in test_impact.render_markdown(clean_report)

    impacted_report = {
        "clean": False,
        "changed_files": ["src/calc.py"],
        "directly_impacted_tests": ["tests/test_calc.py"],
        "transitively_impacted_tests": [],
        "all_impacted_tests": ["tests/test_calc.py"],
        "total_tests_count": 10,
        "selected_tests_count": 1,
        "reduction_pct": 90.0,
        "recommended_pytest_command": "python -m pytest tests/test_calc.py",
        "confidence": "high",
    }
    md = test_impact.render_markdown(impacted_report)
    assert "Directly Impacted Tests (1)" in md
    assert "tests/test_calc.py" in md
    assert "`90.0%` skipped" in md


def test_cli_main(mini_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = test_impact.main(
        [
            "--repo-root",
            str(mini_repo),
            "--files",
            "src/sample/core.py",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["selected_tests_count"] == 2
    assert "tests/test_core.py" in data["all_impacted_tests"]


def test_cli_main_out_file(mini_repo: Path) -> None:
    out_file = mini_repo / "impact.json"
    rc = test_impact.main(
        [
            "--repo-root",
            str(mini_repo),
            "--files",
            "src/sample/service.py",
            "--out",
            str(out_file),
        ]
    )
    assert rc == 0
    assert out_file.is_file()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["selected_tests_count"] == 1
