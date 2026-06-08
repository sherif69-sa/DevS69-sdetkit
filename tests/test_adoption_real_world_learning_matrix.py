from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_real_world_learning_matrix import (
    SCHEMA_VERSION,
    run_real_world_learning_matrix,
    write_real_world_learning_matrix_artifacts,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _repo(root: Path, shape: str) -> None:
    if shape == "python_package":
        _write(root / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
        _write(root / "requirements-test.txt", "pytest==9.0.3\n")
        _write(root / "tests" / "test_demo.py", "def test_demo():\n    assert True\n")
        _write(root / ".github" / "workflows" / "ci.yml", "name: ci\non: [push]\n")
    elif shape == "python_uv_project":
        _write(root / "pyproject.toml", "[project]\nname = 'demo'\n")
        _write(root / "uv.lock", "")
    elif shape == "python_poetry_project":
        _write(root / "pyproject.toml", "[tool.poetry]\nname = 'demo'\n")
        _write(root / "poetry.lock", "")
    elif shape == "javascript_typescript_package":
        _write(root / "package.json", '{"scripts": {"test": "vitest"}}\n')
        _write(root / "package-lock.json", "{}\n")
        _write(root / "tsconfig.json", "{}\n")
    elif shape == "go_module":
        _write(root / "go.mod", "module example.com/demo\n")
    elif shape == "rust_crate":
        _write(root / "Cargo.toml", "[package]\nname = 'demo'\nversion = '0.1.0'\n")
        _write(root / "Cargo.lock", "")
    elif shape == "java_maven_project":
        _write(root / "pom.xml", "<project></project>\n")
    elif shape == "monorepo_workspace":
        _write(root / "package.json", '{"workspaces": ["packages/*"]}\n')
        _write(root / "package-lock.json", "{}\n")
        _write(root / "pyproject.toml", "[project]\nname = 'demo'\n")
    elif shape == "minimal_docs_project":
        _write(root / "mkdocs.yml", "site_name: demo\n")
        _write(root / "docs" / "index.md", "# Demo\n")
    elif shape == "mixed_language_repo":
        _write(root / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
        _write(root / "requirements-test.txt", "pytest\n")
        _write(root / "package.json", '{"scripts": {"test": "npm run unit"}}\n')
        _write(root / "package-lock.json", "{}\n")
        _write(root / ".gitlab-ci.yml", "test:\n  script: echo ok\n")
    else:
        raise AssertionError(shape)


def _matrix(tmp_path: Path) -> tuple[Path, dict[str, dict[str, bytes]]]:
    shapes = [
        "python_package",
        "python_uv_project",
        "python_poetry_project",
        "javascript_typescript_package",
        "go_module",
        "rust_crate",
        "java_maven_project",
        "monorepo_workspace",
        "minimal_docs_project",
        "mixed_language_repo",
    ]

    entries = []
    snapshots: dict[str, dict[str, bytes]] = {}
    for _index, shape in enumerate(shapes, 1):
        root = tmp_path / "targets" / shape
        _repo(root, shape)
        snapshots[shape] = _snapshot(root)
        entries.append(
            {
                "name": shape,
                "target_root": root.as_posix(),
                "repo_url": f"https://example.invalid/{shape}.git",
                "license": "MIT",
                "shape": shape,
            }
        )

    matrix_json = tmp_path / "matrix.json"
    matrix_json.write_text(json.dumps({"repos": entries}), encoding="utf-8")
    return matrix_json, snapshots


def test_real_world_learning_matrix_wraps_external_integration_stack(tmp_path: Path) -> None:
    matrix_json, snapshots = _matrix(tmp_path)
    artifact_root = tmp_path / "artifacts"

    payload = run_real_world_learning_matrix(
        matrix_json=matrix_json,
        artifact_root=artifact_root,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["matrix_status"] == "passed"
    assert payload["repo_count"] == 10
    assert payload["minimum_repos"] == 10
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert payload["rules"]["install_dependencies"] is False
    assert payload["rules"]["target_tests_executed"] is False
    assert payload["rules"]["target_repo_mutation"] is False

    for repo in payload["repos"]:
        assert repo["integration_status"] == "passed"
        assert repo["target_tree_unchanged"] is True
        assert "supported_surface" in repo["learning_observations"]
        assert Path(repo["artifact_paths"]["surface_json"]).is_file()
        assert Path(repo["artifact_paths"]["proof_recommendations_json"]).is_file()
        assert Path(repo["artifact_paths"]["repo_topology_json"]).is_file()
        assert Path(repo["artifact_paths"]["evidence_bundle_json"]).is_file()
        assert Path(repo["artifact_paths"]["external_integration_json"]).is_file()

        root = Path(repo["target_root"])
        assert _snapshot(root) == snapshots[repo["shape"]]

    assert payload["observation_counts"]["supported_surface"] == 10
    assert payload["upgrade_candidates"]
    assert all(candidate["review_first"] is True for candidate in payload["upgrade_candidates"])
    assert all(candidate["safe_to_patch"] is False for candidate in payload["upgrade_candidates"])


def test_real_world_learning_matrix_writes_json_markdown_and_per_repo_artifacts(
    tmp_path: Path,
) -> None:
    matrix_json, _snapshots = _matrix(tmp_path)
    artifact_root = tmp_path / "artifacts"

    payload = write_real_world_learning_matrix_artifacts(
        matrix_json=matrix_json,
        artifact_root=artifact_root,
    )

    json_path = artifact_root / "adoption-real-world-matrix.json"
    markdown_path = artifact_root / "adoption-real-world-matrix.md"

    assert json_path.is_file()
    assert markdown_path.is_file()
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION
    assert "# SDETKit real-world adoption learning matrix" in markdown_path.read_text(
        encoding="utf-8"
    )
    assert payload["repo_count"] == 10
    assert len(list((artifact_root / "per_repo_artifacts").iterdir())) == 10


def test_real_world_learning_matrix_cli_dispatch(tmp_path: Path, capsys) -> None:
    matrix_json, _snapshots = _matrix(tmp_path)
    artifact_root = tmp_path / "artifacts"

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "adoption-real-world-learning-matrix",
            "--matrix-json",
            str(matrix_json),
            "--artifact-root",
            str(artifact_root),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "# SDETKit real-world adoption learning matrix" in stdout
    assert "install_dependencies: false" in stdout
    assert (artifact_root / "adoption-real-world-matrix.json").is_file()
    assert (artifact_root / "adoption-real-world-matrix.md").is_file()
