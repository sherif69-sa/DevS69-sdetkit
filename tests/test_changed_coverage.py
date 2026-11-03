"""Changed-line coverage in `sdetkit verify change`: which of a change's lines its tests run."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sdetkit import change_verifier, changed_coverage, mcp_server

needs_coverage = pytest.mark.skipif(
    shutil.which("git") is None
    or importlib.util.find_spec("coverage") is None
    or importlib.util.find_spec("pytest_cov") is None,
    reason="needs git, coverage and pytest-cov",
)
needs_go = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("go") is None, reason="needs git and go"
)

DIFF = """\
diff --git a/src/calc.py b/src/calc.py
index 1111111..2222222 100644
--- a/src/calc.py
+++ b/src/calc.py
@@ -1,4 +1,5 @@
 def add(a, b):
-    return a + b
+    total = a + b
+    return total


@@ -10,2 +11,3 @@ def sub(a, b):
     return a - b
+# the end
\\ No newline at end of file
diff --git a/src/new.py b/src/new.py
new file mode 100644
--- /dev/null
+++ b/src/new.py
@@ -0,0 +1,2 @@
+def mul(a, b):
+    return a * b
diff --git a/src/gone.py b/src/gone.py
deleted file mode 100644
--- a/src/gone.py
+++ /dev/null
@@ -1 +0,0 @@
-x = 1
diff --git a/tests/test_calc.py b/tests/test_calc.py
--- a/tests/test_calc.py
+++ b/tests/test_calc.py
@@ -1 +1,2 @@
 import calc
+++counter
diff --git "a/src/caf\\303\\251.py" "b/src/caf\\303\\251.py"
--- "a/src/caf\\303\\251.py"
+++ "b/src/caf\\303\\251.py"
@@ -1 +1 @@
-a = 1
+a = 2
"""


def test_the_diff_gives_the_changed_lines_of_kept_files() -> None:
    lines = changed_coverage.changed_lines(DIFF, lambda path: not path.startswith("tests/"))

    assert lines == {
        "src/calc.py": [2, 3, 12],
        "src/new.py": [1, 2],
        "src/café.py": [1],
    }


def test_line_ranges_and_the_go_profile() -> None:
    assert changed_coverage.line_ranges([9, 3, 4, 5, 11, 12]) == "3-5, 9, 11-12"
    assert changed_coverage.line_ranges([]) == ""
    profile = (
        "mode: set\n"
        "example.com/m/calc/calc.go:3.24,5.2 2 1\n"
        "example.com/m/calc/calc.go:7.24,9.2 1 0\n"
        "example.com/m/calc/calc.go:9.2,9.10 0 0\n"
        "example.com/m/main.go:1.1,2.2 1 1\n"
    )

    measured = changed_coverage.read_go_profile(profile, "example.com/m")

    assert measured == {
        "calc/calc.go": ({3, 4, 5, 7, 8, 9}, {3, 4, 5}),
        "main.go": ({1, 2}, {1, 2}),
    }


def test_coverage_json_paths_read_relative_to_the_clone(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(
        json.dumps(
            {
                "files": {
                    str(tmp_path / "src" / "a.py"): {"executed_lines": [1], "missing_lines": [3]},
                    "src/b.py": {"executed_lines": [], "missing_lines": [1, 2]},
                    "/elsewhere/c.py": {"executed_lines": [1], "missing_lines": []},
                }
            }
        ),
        encoding="utf-8",
    )

    assert changed_coverage.read_coverage_json(report, tmp_path) == {
        "src/a.py": ({1, 3}, {1}),
        "src/b.py": ({1, 2}, set()),
    }


def test_the_summary_counts_code_lines_only_and_lists_the_ones_not_run() -> None:
    summary = changed_coverage.summarize(
        {"src/a.py": [1, 2, 3, 4], "src/doc.py": [1], "src/far.go": [5]},
        {"src/a.py": ({1, 3, 4}, {1}), "src/doc.py": (set(), set())},
        tool="coverage.py",
        minimum=50,
    )

    assert (summary["changed_lines"], summary["run_lines"], summary["percent"]) == (3, 1, 33.3)
    assert summary["files"] == [{"path": "src/a.py", "changed": 3, "run": 1, "not_run": [3, 4]}]
    assert summary["unmeasured"] == ["src/far.go"]
    assert changed_coverage.not_run_items(summary) == ["src/a.py:3-4"]
    assert changed_coverage.coverage_line(summary) == (
        "**Changed lines:** the tests run 1 of the 3 changed line(s) of code (33.3%)."
    )
    assert changed_coverage.coverage_line(changed_coverage.summarize({}, {}, tool="")) == ""


def test_findings_note_by_default_and_block_below_the_minimum() -> None:
    measured = {"src/a.py": ({1, 2}, {1})}
    note = change_verifier.coverage_findings(
        changed_coverage.summarize({"src/a.py": [1, 2]}, measured, tool="coverage.py")
    )
    blocking = change_verifier.coverage_findings(
        changed_coverage.summarize({"src/a.py": [1, 2]}, measured, tool="coverage.py", minimum=80)
    )
    unknown = change_verifier.coverage_findings(
        changed_coverage.not_measured("not measured for jest yet", minimum=80)
    )
    quiet = change_verifier.coverage_findings(
        changed_coverage.not_measured("not measured for jest yet")
    )

    assert [(f["code"], f["blocking"], f["items"]) for f in note] == [
        ("changed_lines_not_run", False, ["src/a.py:2"])
    ]
    assert blocking[0]["blocking"] is True
    assert "50% of them run; the minimum is 80%." in blocking[0]["message"]
    assert [(f["code"], f["blocking"]) for f in unknown] == [("changed_lines_not_measured", True)]
    assert "not measured for jest yet" in unknown[0]["message"]
    assert quiet == []


def test_what_counts_as_code_and_what_reads_as_unknown(tmp_path: Path) -> None:
    python, go = change_verifier._source_file("pytest"), change_verifier._source_file("go")

    assert python("src/calc.py") and go("calc/calc.go")
    assert not any(
        python(path)
        for path in ("tests/test_calc.py", "src/test_x.py", "conftest.py", "vendor/x.py", "a.go")
    )
    assert not any(go(path) for path in ("calc/calc_test.go", "testdata/x.go", "vendor/m/x.go"))
    assert changed_coverage.read_coverage_json(tmp_path / "missing.json", tmp_path) == {}
    assert changed_coverage.coverage_line(None) == ""
    assert changed_coverage.coverage_line(changed_coverage.not_measured("turned off")) == (
        "**Changed lines:** not measured (turned off)."
    )
    unmeasured = change_verifier.coverage_findings(
        changed_coverage.summarize({"pkg/x.go": [3]}, {}, tool="go test -coverprofile")
    )
    assert [(f["code"], f["blocking"], f["items"]) for f in unmeasured] == [
        ("changed_files_not_measured", False, ["pkg/x.go"])
    ]


@pytest.mark.parametrize("minimum", [-1, 100.5])
def test_the_minimum_is_a_percentage(tmp_path: Path, minimum: float) -> None:
    with pytest.raises(change_verifier.ChangeError, match="percentage"):
        change_verifier.verify_change(repo_root=tmp_path, head="HEAD", min_changed_coverage=minimum)


def test_the_mcp_tool_takes_a_minimum_and_returns_the_lines_not_run() -> None:
    assert mcp_server._percent(None) == 0.0
    assert mcp_server._percent(80) == 80.0
    for bad in (101, -1, "80", True):
        with pytest.raises(mcp_server.ToolError):
            mcp_server._percent(bad)
    coverage = changed_coverage.summarize(
        {"src/a.py": [1, 2]}, {"src/a.py": ({1, 2}, {1})}, tool="coverage.py"
    )

    assert mcp_server._changed_lines(coverage) == {
        "measured": True,
        "percent": 50.0,
        "not_run": {"src/a.py": [2]},
        "reason": "",
    }


# --- end to end ---------------------------------------------------------------------------

CALC = "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"
CHANGED = (
    "def add(a, b):\n    # adds two numbers\n    total = a + b\n    return total\n\n\n"
    "def sub(a, b):\n    if a < b:\n        return -(b - a)\n    return a - b\n"
)
TEST = "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _python_repo(tmp_path: Path, pytest_options: str = "") -> Path:
    repo = tmp_path / "repo"
    files = {
        "pyproject.toml": '[project]\nname = "calc"\nversion = "0"\n'
        f'[tool.pytest.ini_options]\npythonpath = ["src"]\n{pytest_options}',
        "src/calc/__init__.py": CALC,
        "tests/test_calc.py": TEST,
    }
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def _patch(repo: Path, files: dict[str, str]) -> str:
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    diff = _git(repo, "diff", "--cached")
    _git(repo, "reset", "-q", "--hard")
    _git(repo, "clean", "-qfd")
    return diff


@needs_coverage
@pytest.mark.parametrize("pytest_options", ["", 'addopts = "--cov=calc --cov-fail-under=100"\n'])
def test_lines_no_test_runs_are_reported_and_can_block(tmp_path: Path, pytest_options: str) -> None:
    repo = _python_repo(tmp_path, pytest_options)
    diff = _patch(
        repo,
        {
            "src/calc/__init__.py": CHANGED,
            "src/calc/extra.py": "def mul(a, b):\n    return a * b\n",
        },
    )

    noted = change_verifier.verify_change(
        repo_root=repo, out_dir=tmp_path / "a", python=sys.executable, patch_text=diff
    )
    blocked = change_verifier.verify_change(
        repo_root=repo,
        out_dir=tmp_path / "b",
        python=sys.executable,
        patch_text=diff,
        min_changed_coverage=80,
    )

    coverage = noted["changed_coverage"]
    assert noted["status"] == "VERIFIED", noted["reasons"]
    assert (coverage["tool"], coverage["changed_lines"], coverage["run_lines"]) == (
        "coverage.py",
        6,
        2,
    )
    assert changed_coverage.not_run_items(coverage) == [
        "src/calc/__init__.py:8-9",
        "src/calc/extra.py:1-2",
    ]
    assert blocked["status"] == "REVIEW"
    assert blocked["reasons"][0].startswith("changed_lines_not_run:")
    predicate = json.loads((tmp_path / "b" / "change-verification.predicate.json").read_text())
    assert predicate["changed_lines"] == {
        "measured": True,
        "changed_lines": 6,
        "run_lines": 2,
        "percent": 33.3,
        "minimum": 80.0,
    }
    assert "**Changed lines:** the tests run 2 of the 6" in (
        tmp_path / "a" / "change-verification.md"
    ).read_text(encoding="utf-8")
    # The probe file is gone and nothing was left in the repository.
    assert not _git(repo, "status", "--porcelain")


@needs_coverage
def test_a_change_to_tests_only_has_nothing_to_measure(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    diff = _patch(
        repo, {"tests/test_calc.py": TEST + "\n\ndef test_zero():\n    assert add(0, 0) == 0\n"}
    )

    report = change_verifier.verify_change(
        repo_root=repo,
        out_dir=tmp_path / "out",
        python=sys.executable,
        patch_text=diff,
        min_changed_coverage=90,
    )

    assert report["status"] == "VERIFIED", report["reasons"]
    assert report["changed_coverage"]["changed_lines"] == 0
    assert report["changed_coverage"]["percent"] is None


def test_an_interpreter_without_coverage_is_not_measured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if shutil.which("git") is None:
        pytest.skip("needs git")
    repo = _python_repo(tmp_path)
    diff = _patch(repo, {"src/calc/__init__.py": CHANGED})
    # The interpreter that runs the tests has pytest but not coverage.py.
    monkeypatch.setattr(change_verifier, "_importable", lambda python, module: False)

    report = change_verifier.verify_change(
        repo_root=repo, out_dir=tmp_path / "out", python=sys.executable, patch_text=diff
    )

    off = change_verifier.verify_change(
        repo_root=repo,
        out_dir=tmp_path / "off",
        python=sys.executable,
        patch_text=diff,
        measure_coverage=False,
    )

    assert report["status"] == "VERIFIED", report["reasons"]
    assert report["changed_coverage"]["measured"] is False
    assert "coverage.py is not installed" in report["changed_coverage"]["reason"]
    assert off["changed_coverage"]["reason"] == "turned off with --no-coverage"


GO_CALC = "package calc\n\nfunc Add(a, b int) int { return a + b }\n\nfunc Sub(a, b int) int {\n\treturn a - b\n}\n"
GO_CHANGED = (
    "package calc\n\nfunc Add(a, b int) int {\n\ts := a + b\n\treturn s\n}\n\n"
    "func Sub(a, b int) int {\n\tif a < b {\n\t\treturn -(b - a)\n\t}\n\treturn a - b\n}\n"
)
GO_TEST = (
    'package calc\n\nimport "testing"\n\n'
    'func TestAdd(t *testing.T) {\n\tif Add(2, 3) != 5 {\n\t\tt.Fatal("no")\n\t}\n}\n'
)


@needs_go
def test_go_changed_lines_count_across_packages(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    files = {
        "go.mod": "module example.com/calc\n\ngo 1.21\n",
        "calc/calc.go": GO_CALC,
        "calc/calc_test.go": GO_TEST,
        "other/other.go": "package other\n\nfunc One() int { return 1 }\n",
    }
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    diff = _patch(
        repo,
        {
            "calc/calc.go": GO_CHANGED,
            "other/other.go": "package other\n\nfunc One() int { return 2 - 1 }\n",
        },
    )

    report = change_verifier.verify_change(
        repo_root=repo, out_dir=tmp_path / "out", python=sys.executable, patch_text=diff
    )

    coverage = report["changed_coverage"]
    assert report["status"] == "VERIFIED", report["reasons"]
    assert coverage["tool"] == "go test -coverprofile"
    assert (coverage["changed_lines"], coverage["run_lines"]) == (8, 4)
    assert changed_coverage.not_run_items(coverage) == ["calc/calc.go:9-11", "other/other.go:3"]
