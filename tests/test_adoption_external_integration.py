from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.adoption_external_integration import (
    SCHEMA_VERSION,
    run_external_integration,
    write_external_integration_artifact,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_external_python_repo(root: Path) -> None:
    _write(
        root / ".git" / "config",
        '[remote "origin"]\n\turl = https://github.com/pallets/click.git\n',
    )
    _write(root / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(root / "requirements-test.txt", "pytest==9.0.3\n")
    _write(root / "tests" / "test_demo.py", "def test_demo():\n    assert True\n")
    _write(root / ".github" / "workflows" / "tests.yml", "name: tests\non: [push]\n")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_external_integration_runner_writes_artifacts_outside_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "external_repo"
    artifacts = tmp_path / "artifacts"
    _make_external_python_repo(target)
    before = _snapshot(target)

    payload = write_external_integration_artifact(
        target_root=target,
        artifact_dir=artifacts,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["integration_status"] == "passed"
    assert payload["target_tree_unchanged"] is True
    assert _snapshot(target) == before

    for artifact_path in payload["artifact_paths"].values():
        path = Path(artifact_path)
        assert path.is_file()
        assert not path.is_relative_to(target)

    assert payload["bundle_status"] == "adoption_evidence_bundle_generated"
    assert payload["rules"]["artifacts_outside_target_root"] is True
    assert payload["rules"]["no_dependency_install"] is True
    assert payload["rules"]["no_target_tests_executed"] is True
    assert payload["rules"]["no_target_repo_mutation"] is True
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_external_integration_rejects_artifacts_inside_target(tmp_path: Path) -> None:
    target = tmp_path / "external_repo"
    _make_external_python_repo(target)

    with pytest.raises(ValueError, match="artifact_dir must be outside target_root"):
        run_external_integration(
            target_root=target,
            artifact_dir=target / "build" / "sdetkit",
        )


def test_external_integration_cli_dispatch_remains_hidden_but_callable(
    tmp_path: Path,
    capsys,
) -> None:
    target = tmp_path / "external_repo"
    artifacts = tmp_path / "artifacts"
    out = artifacts / "external-integration.json"
    _make_external_python_repo(target)

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "adoption-external-integration",
            "--target-root",
            str(target),
            "--artifact-dir",
            str(artifacts),
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert "adoption_external_integration_status=passed" in stdout
    assert "target_tree_unchanged=true" in stdout
    assert "- no_target_repo_mutation=true" in stdout
    assert "- patch_application_allowed=false" in stdout
