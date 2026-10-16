"""`kits radar` and `kits route-map` answer from the repository, not fixed values.

They used to return `runtime_core_packages: 1`, one "Dependency risk" card, the query
echoed as the only hotspot and `pytest -q` as every package's validation, and they matched
files by substring (a comment mentioning httpx counted as using it).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import kits
from sdetkit.dependency_map import NARROW_TEST_LIMIT, build_map, declared_dependencies

PYPROJECT = """\
[project]
name = "demo"
version = "0.1.0"
dependencies = ["httpx>=0.28,<1", "rich>=13", "unusedlib==1.0"]

[project.optional-dependencies]
docs = ["mkdocs==1.6.1"]
all = ["demo[docs]"]

[dependency-groups]
test = ["pytest>=9", {include-group = "lint"}]
lint = ["ruff"]
"""


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return _write(
        tmp_path,
        {
            "pyproject.toml": PYPROJECT,
            "uv.lock": (
                'version = 1\n\n[[package]]\nname = "httpx"\nversion = "0.28.1"\n\n'
                '[[package]]\nname = "rich"\nversion = "13.9.0"\n'
            ),
            "src/demo/api.py": "import httpx\nfrom rich.console import Console\n",
            "src/demo/client.py": "from httpx import Client\nfrom . import api\n",
            "src/demo/notes.py": "# httpx is mentioned here but never imported\nURL = 'httpx'\n",
            "src/demo/cli.py": "import httpx.auth\n",
            "tests/test_api.py": "import httpx\nimport pytest\n",
            "tests/conftest.py": "import pytest\n",
            "tests/helpers.py": "import httpx\n",
            "tests/fixtures/sample/test_fixture.py": "import rich\n",
            "examples/nested/pyproject.toml": '[project]\nname = "nested"\n',
            "examples/nested/test_nested.py": "import rich\n",
            "src/demo/broken.py": "def (:\n",
        },
    )


def test_declared_dependencies_cover_runtime_extras_and_groups(repo: Path) -> None:
    declared = declared_dependencies(repo)

    assert declared["httpx"] == ("httpx>=0.28,<1", ["runtime"])
    assert declared["mkdocs"][1] == ["docs"]
    assert declared["pytest"][1] == ["test"]
    assert declared["ruff"][1] == ["lint"]
    assert "demo" not in declared  # the `demo[docs]` self-reference


def test_usage_comes_from_imports_in_the_repository_s_own_files(repo: Path) -> None:
    dep_map = build_map(repo)
    deps = {d.name: d for d in dep_map.dependencies}

    # `import httpx.auth` and `from httpx import` count; a comment and a string do not.
    assert deps["httpx"].files == (
        "src/demo/api.py",
        "src/demo/cli.py",
        "src/demo/client.py",
        "tests/helpers.py",
        "tests/test_api.py",
    )
    # Collectable test files only: no conftest.py or helpers.
    assert deps["httpx"].test_files == ("tests/test_api.py",)
    # Fixtures and nested projects are not the repository's code.
    assert deps["rich"].files == ("src/demo/api.py",)
    assert deps["unusedlib"].files == ()
    assert (deps["httpx"].locked, deps["rich"].locked, deps["mkdocs"].locked) == (
        "0.28.1",
        "13.9.0",
        None,
    )
    assert dep_map.errors == ["src/demo/broken.py: SyntaxError"]


def test_validation_is_the_narrowest_command_that_runs_the_package_s_tests(repo: Path) -> None:
    deps = {d.name: d for d in build_map(repo).dependencies}

    assert deps["httpx"].tier == "hot-path"
    assert deps["httpx"].primary_validation() == "python -m pytest -q tests/test_api.py"
    assert deps["rich"].primary_validation() == "python -m sdetkit gate fast"

    many = {f"tests/test_{i}.py": "import rich\n" for i in range(NARROW_TEST_LIMIT + 1)}
    _write(repo, many)
    rich = next(d for d in build_map(repo).dependencies if d.name == "rich")
    assert rich.primary_validation() == "python -m sdetkit gate fast --only pytest"


def test_radar_reports_real_counts_and_watchlists(repo: Path) -> None:
    payload = kits.radar_payload(repo, "", "balanced", "all", limit=5)

    metrics = payload["headline_metrics"]
    assert (metrics["packages_audited"], metrics["runtime_core_packages"]) == (6, 3)
    assert metrics["locked_packages"] == 2
    assert payload["watchlists"]["unused_runtime"] == ["unusedlib"]
    assert payload["watchlists"]["not_locked"] == ["mkdocs", "pytest", "ruff", "unusedlib"]
    assert payload["hotspots"][0]["package"] == "httpx"
    assert payload["maintenance_lanes"][0]["commands"][0] == (
        "python -m pytest -q tests/test_api.py"
    )
    titles = {card["title"]: card["count"] for card in payload["dashboard_cards"]}
    assert titles["Runtime dependencies never imported"] == 1


def test_filters_select_by_name_group_tier_and_usage(repo: Path) -> None:
    def names(query: str = "", tier: str = "balanced", area: str = "all") -> list[str]:
        payload = kits.route_map_payload(repo, query, tier, area, limit=10)
        return [match["package"] for match in payload["matches"]]

    assert names("http") == ["httpx"]
    assert names(area="runtime-core") == ["httpx", "rich", "unusedlib"]
    assert names(area="docs") == ["mkdocs"]
    assert names(tier="hot-path") == ["httpx"]
    assert names(tier="edge") == ["mkdocs", "rich", "ruff", "unusedlib"]  # pytest: 2 files
    assert names("cli.py") == ["httpx"]  # a token found in a usage path


def test_the_cli_prints_readable_text(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert kits.main(["radar", "--repo-root", str(repo)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("dependency radar: 6 declared, 3 runtime, 1 hot-path, 2 locked (uv.lock)")
    assert "  httpx: 5 files (1 tests) -> python -m pytest -q tests/test_api.py" in out

    assert kits.main(["route-map", "httpx", "--repo-root", str(repo), "--format", "json"]) == 0
    match = json.loads(capsys.readouterr().out)["matches"][0]
    assert match["alternate_validation"] == [
        "python -m sdetkit gate fast --only pytest",
        "python -m sdetkit gate fast",
    ]


def test_a_repository_without_declared_dependencies_says_so(tmp_path: Path) -> None:
    payload = kits.radar_payload(tmp_path, "", "balanced", "all")

    assert payload["status"] == "no_declared_dependencies"
    assert payload["hotspots"] == []
