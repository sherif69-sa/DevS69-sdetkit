from __future__ import annotations

from pathlib import Path

import pytest

from sdetkit.projects import discover_projects, resolve_project


def _write_pyproject(d: Path, name: str) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )


def test_autodiscover_packages_ignores_node_modules(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _write_pyproject(repo / "packages" / "a", "pkg-a")
    _write_pyproject(repo / "packages" / "b", "pkg-b")
    _write_pyproject(repo / "node_modules" / "junk", "junk-should-not-appear")

    source, projects = discover_projects(repo, sort=True)
    assert source == "autodiscover"
    assert [(p.name, p.root) for p in projects] == [
        ("pkg-a", "packages/a"),
        ("pkg-b", "packages/b"),
    ]

    resolved = [resolve_project(repo, p) for p in projects]
    assert [r.root_rel for r in resolved] == ["packages/a", "packages/b"]
    assert resolved[0].baseline_rel == "packages/a/.sdetkit/audit-baseline.json"


def test_pyproject_autodiscover_with_custom_roots_and_stable_order(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_pyproject(repo / "services" / "api", "svc-api")
    _write_pyproject(repo / "libs" / "core", "lib-core")
    (repo / "pyproject.toml").write_text(
        """
[tool.sdetkit.projects]
autodiscover = true
autodiscover_roots = ["services", "libs", "services"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    source, projects = discover_projects(repo, sort=True)
    assert source == "pyproject.toml (autodiscover)"
    assert [(p.name, p.root) for p in projects] == [
        ("lib-core", "libs/core"),
        ("svc-api", "services/api"),
    ]


def test_pyproject_autodiscover_validates_boolean_and_roots_type(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "pyproject.toml").write_text(
        """
[tool.sdetkit.projects]
autodiscover = "yes"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="autodiscover must be a boolean"):
        discover_projects(repo)

    (repo / "pyproject.toml").write_text(
        """
[tool.sdetkit.projects]
autodiscover = true
autodiscover_roots = 12
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="autodiscover_roots"):
        discover_projects(repo)


def test_pyproject_merges_manifest_projects_with_autodiscovered_entries(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_pyproject(repo / "services" / "api", "svc-api")
    _write_pyproject(repo / "libs" / "core", "lib-core")
    (repo / "pyproject.toml").write_text(
        """
[tool.sdetkit.projects]
autodiscover = true
autodiscover_roots = ["services", "libs"]

[[tool.sdetkit.projects.project]]
name = "ops"
root = "ops/tools"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    source, projects = discover_projects(repo, sort=False)
    assert source == "pyproject.toml"
    assert [(p.name, p.root) for p in projects] == [
        ("ops", "ops/tools"),
        ("lib-core", "libs/core"),
        ("svc-api", "services/api"),
    ]


def test_pyproject_manifest_entries_override_autodiscovered_duplicates(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_pyproject(repo / "services" / "api", "svc-api")
    (repo / "pyproject.toml").write_text(
        """
[tool.sdetkit.projects]
autodiscover = true
autodiscover_roots = ["services"]

[[tool.sdetkit.projects.project]]
name = "svc-api"
root = "services/api"
packs = ["security"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    _, projects = discover_projects(repo)
    assert [(p.name, p.root, p.packs) for p in projects] == [
        ("svc-api", "services/api", ("security",)),
    ]


def test_pyproject_manifest_rejects_duplicate_normalized_roots(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        """
[tool.sdetkit.projects]

[[tool.sdetkit.projects.project]]
name = "api"
root = "services/api"

[[tool.sdetkit.projects.project]]
name = "api-dup"
root = "./services/api"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate project root: services/api"):
        discover_projects(repo)


def test_autodiscover_supports_poetry_and_pdm_names(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    poetry = repo / "packages" / "poetry-lib"
    poetry.mkdir(parents=True)
    (poetry / "pyproject.toml").write_text(
        """
[tool.poetry]
name = "poetry-lib"
version = "0.1.0"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    pdm = repo / "packages" / "pdm-svc"
    pdm.mkdir(parents=True)
    (pdm / "pyproject.toml").write_text(
        """
[tool.pdm]
name = "pdm-svc"
version = "0.2.0"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    source, projects = discover_projects(repo, sort=True)
    assert source == "autodiscover"
    assert [(p.name, p.root) for p in projects] == [
        ("pdm-svc", "packages/pdm-svc"),
        ("poetry-lib", "packages/poetry-lib"),
    ]


def test_autodiscover_prefers_pep621_name_when_multiple_metadata_sections_exist(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    pkg = repo / "packages" / "mixed"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        """
[project]
name = "pep621-name"
version = "1.0.0"

[tool.poetry]
name = "poetry-name"
version = "1.0.0"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    _, projects = discover_projects(repo)
    assert [(p.name, p.root) for p in projects] == [("pep621-name", "packages/mixed")]


def test_autodiscover_detects_node_package_json_projects(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    web = repo / "apps" / "web"
    web.mkdir(parents=True)
    (web / "package.json").write_text(
        '{"name": "@acme/web", "private": true}',
        encoding="utf-8",
    )

    api = repo / "packages" / "api"
    api.mkdir(parents=True)
    (api / "package.json").write_text(
        '{"name": "acme-api", "version": "1.0.0"}',
        encoding="utf-8",
    )

    _, projects = discover_projects(repo, sort=True)
    assert [(p.name, p.root) for p in projects] == [
        ("@acme/web", "apps/web"),
        ("acme-api", "packages/api"),
    ]


def test_autodiscover_prefers_pyproject_name_when_package_json_is_also_present(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    svc = repo / "packages" / "svc"
    svc.mkdir(parents=True)
    (svc / "pyproject.toml").write_text(
        '[project]\nname = "python-name"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    (svc / "package.json").write_text(
        '{"name": "node-name"}',
        encoding="utf-8",
    )

    _, projects = discover_projects(repo)
    assert [(p.name, p.root) for p in projects] == [("python-name", "packages/svc")]


def test_autodiscover_detects_rust_and_go_projects(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    rust = repo / "packages" / "worker"
    rust.mkdir(parents=True)
    (rust / "Cargo.toml").write_text(
        """
[package]
name = "acme-worker"
version = "0.1.0"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    gomod = repo / "apps" / "gateway"
    gomod.mkdir(parents=True)
    (gomod / "go.mod").write_text(
        "module github.com/acme/gateway\n\ngo 1.22\n",
        encoding="utf-8",
    )

    source, projects = discover_projects(repo, sort=True)
    assert source == "autodiscover"
    assert [(p.name, p.root) for p in projects] == [
        ("acme-worker", "packages/worker"),
        ("github.com/acme/gateway", "apps/gateway"),
    ]


def test_autodiscover_prefers_pyproject_before_cargo_and_go_before_package_json(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    hybrid = repo / "packages" / "hybrid"
    hybrid.mkdir(parents=True)
    (hybrid / "pyproject.toml").write_text(
        '[project]\nname = "py-name"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    (hybrid / "Cargo.toml").write_text(
        """
[package]
name = "cargo-name"
version = "0.1.0"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    edge = repo / "apps" / "edge"
    edge.mkdir(parents=True)
    (edge / "go.mod").write_text("module github.com/acme/edge\n", encoding="utf-8")
    (edge / "package.json").write_text('{"name": "node-edge"}', encoding="utf-8")

    _, projects = discover_projects(repo, sort=True)
    assert [(p.name, p.root) for p in projects] == [
        ("github.com/acme/edge", "apps/edge"),
        ("py-name", "packages/hybrid"),
    ]


def test_autodiscover_duplicate_name_error_includes_both_roots_in_stable_order(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _write_pyproject(repo / "packages" / "zeta", "shared-name")
    _write_pyproject(repo / "packages" / "alpha", "shared-name")

    with pytest.raises(
        ValueError,
        match=r"duplicate project name: shared-name \(roots: packages/alpha and packages/zeta\)",
    ):
        discover_projects(repo)
