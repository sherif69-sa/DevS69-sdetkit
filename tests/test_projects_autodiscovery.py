from __future__ import annotations

from pathlib import Path

from sdetkit.projects import discover_projects


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_autodiscover_mixed_monorepo_is_deterministic(tmp_path: Path) -> None:
    _write(tmp_path / "pkgA" / "pyproject.toml", "[project]\nname='a'\n")
    _write(tmp_path / "pkgB" / "pyproject.toml", "[project]\nname='b'\n")
    _write(
        tmp_path / "package.json",
        '{"name":"root","private":true,"workspaces":["packages/*"]}\n',
    )
    _write(tmp_path / "packages" / "pkg1" / "package.json", '{"name":"pkg1"}\n')
    _write(tmp_path / "services" / "s1" / "go.mod", "module example/s1\n")
    _write(
        tmp_path / "Cargo.toml",
        "[workspace]\nmembers=['crates/*']\n",
    )
    _write(tmp_path / "crates" / "c1" / "Cargo.toml", "[package]\nname='c1'\nversion='0.1.0'\n")

    first_source, first_projects = discover_projects(tmp_path)
    second_source, second_projects = discover_projects(tmp_path)

    assert first_source == "auto-discovered"
    assert [(p.name, p.root, p.config_path) for p in first_projects] == [
        (p.name, p.root, p.config_path) for p in second_projects
    ]
    assert [p.root for p in first_projects] == [
        ".",
        ".",
        "crates/c1",
        "packages/pkg1",
        "pkgA",
        "pkgB",
        "services/s1",
    ]
    assert [p.name for p in first_projects] == [
        "node",
        "rust",
        "rust:crates/c1",
        "node:packages/pkg1",
        "python:pkgA",
        "python:pkgB",
        "go:services/s1",
    ]


def test_autodiscover_dedupes_same_python_root(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "pyproject.toml", "[project]\nname='pkg'\n")
    _write(tmp_path / "pkg" / "requirements.txt", "pytest\n")
    _write(tmp_path / "pkg" / "requirements-dev.txt", "ruff\n")

    _, projects = discover_projects(tmp_path)

    python_projects = [p for p in projects if p.name.startswith("python")]
    assert len(python_projects) == 1
    assert python_projects[0].root == "pkg"
    assert python_projects[0].config_path == "pkg/pyproject.toml"


def test_autodiscover_tooling_folder_without_manifest_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "README.md", "docs\n")
    _write(tmp_path / "scripts" / "lint.sh", "#!/usr/bin/env bash\n")
    _write(tmp_path / ".github" / "workflows" / "ci.yml", "name: ci\n")

    _, projects = discover_projects(tmp_path)

    assert projects == []


def test_autodiscover_tooling_folder_with_real_manifest_is_counted(tmp_path: Path) -> None:
    _write(tmp_path / "tools" / "pkg" / "package.json", '{"name":"toolpkg"}\n')

    _, projects = discover_projects(tmp_path)

    assert [p.name for p in projects] == ["node:tools/pkg"]
    assert [p.root for p in projects] == ["tools/pkg"]


def test_autodiscover_nested_workspace_and_standalone_manifest(tmp_path: Path) -> None:
    _write(tmp_path / "package.json", '{"private":true,"workspaces":["packages/*"]}\n')
    _write(tmp_path / "packages" / "pkg1" / "package.json", '{"name":"pkg1"}\n')
    _write(tmp_path / "packages" / "pkg1" / "requirements.txt", "pytest\n")

    _, projects = discover_projects(tmp_path)

    assert [(p.name, p.root) for p in projects] == [
        ("node", "."),
        ("node:packages/pkg1", "packages/pkg1"),
        ("python:packages/pkg1", "packages/pkg1"),
    ]
