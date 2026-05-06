from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sdetkit import investigate


def test_repo_investigation_json_and_markdown(tmp_path):
    # Create a fake repo tree
    root = tmp_path
    src = root / "src"
    src.mkdir()
    (src / "module_a.py").write_text("def foo(): pass\n", encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_module_a.py").write_text("def test_foo(): assert True\n", encoding="utf-8")
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI\n", encoding="utf-8")

    # JSON output
    result_json = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "investigate",
            "repo",
            "--root",
            str(root),
            "--format",
            "json",
        ],
        cwd=Path.cwd(),
        env=dict(PYTHONPATH="src", **dict(os.environ)),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result_json.returncode == 0
    payload_json = json.loads(result_json.stdout)
    assert payload_json["schema_version"] == "sdetkit.investigate.repo.v1"
    assert payload_json["repo_shape"]["source_files"] == 1
    assert payload_json["repo_shape"]["test_files"] == 1
    assert payload_json["repo_shape"]["workflow_files"] == 1

    # Markdown output
    result_md = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "investigate",
            "repo",
            "--root",
            str(root),
            "--format",
            "markdown",
        ],
        cwd=Path.cwd(),
        env=dict(PYTHONPATH="src", **dict(os.environ)),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result_md.returncode == 0
    md_output = result_md.stdout.lower()
    assert "repository investigation" in md_output
    assert "source files: **1**" in md_output
    assert "test files: **1**" in md_output
    assert "workflow files: **1**" in md_output