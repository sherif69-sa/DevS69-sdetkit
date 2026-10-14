from __future__ import annotations

import json
from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _snapshot_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file()
    }


def _make_external_python_repo(root: Path) -> None:
    _write(
        root / ".git" / "config",
        '[remote "origin"]\n\turl = https://github.com/pallets/click.git\n',
    )
    _write(root / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(root / "requirements-test.txt", "pytest==9.0.3\n")
    _write(root / "tests" / "test_demo.py", "def test_demo():\n    assert True\n")
    _write(root / ".github" / "workflows" / "tests.yml", "name: tests\non: [push]\n")


def test_public_trial_matrix_declares_real_external_stack_intent() -> None:
    payload = json.loads(
        Path("tests/fixtures/adoption_public_trials/public_repo_trial_matrix.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["trial_mode"] == "manual_read_only_public_repo_matrix"
    assert payload["source_code_vendored"] is False
    assert payload["dependency_install_performed"] is False
    assert payload["target_tests_executed"] is False
    assert payload["target_repo_mutated"] is False
    assert payload["target_pr_or_issue_opened"] is False
    assert payload["endorsement_claimed"] is False
    assert len(payload["trials"]) >= 3
