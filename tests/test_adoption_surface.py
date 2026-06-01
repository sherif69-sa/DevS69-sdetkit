from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_surface import SCHEMA_VERSION, discover_adoption_surface


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _names(items: list[dict]) -> set[str]:
    return {str(item["name"]) for item in items}


def _commands(payload: dict) -> set[str]:
    return {str(item["command"]) for item in payload["recommended_proof_commands"]}


def test_adoption_surface_detects_python_github_security_and_proof_commands(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    _write(tmp_path / ".pre-commit-config.yaml", "repos: []\n")
    _write(tmp_path / "mkdocs.yml", "site_name: Example\n")
    _write(tmp_path / "src" / "sdetkit" / "__init__.py")
    _write(
        tmp_path / ".github" / "workflows" / "security.yml",
        "steps:\n  - uses: github/codeql-action/init@abc\n  - uses: actions/dependency-review-action@abc\n",
    )

    payload = discover_adoption_surface(tmp_path)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert "python" in _names(payload["detected_languages"])
    assert "pip" in _names(payload["package_managers"])
    assert "pytest" in _names(payload["test_runners"])
    assert "github_actions" in _names(payload["ci_systems"])
    assert {"codeql", "dependency_review"} <= _names(payload["security_tools"])
    assert "python -m pytest -q -o addopts=" in _commands(payload)
    assert "python -m pre_commit run -a" in _commands(payload)
    assert "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict" in _commands(payload)


def test_adoption_surface_marks_unknown_javascript_test_command_review_first(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "package.json",
        json.dumps({"name": "demo", "scripts": {"build": "tsc"}}),
    )
    _write(tmp_path / "package-lock.json", "{}\n")

    payload = discover_adoption_surface(tmp_path)

    assert "javascript_typescript" in _names(payload["detected_languages"])
    assert "npm" in _names(payload["package_managers"])
    assert payload["test_runners"] == []
    assert payload["review_first_unknowns"] == [
        "JavaScript/TypeScript package manifest detected but test command is not proven"
    ]


def test_adoption_surface_detects_multi_language_evidence_without_running_commands(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "go.mod", "module example\n")
    _write(tmp_path / "Cargo.toml", "[package]\nname = 'example'\n")
    _write(tmp_path / "pom.xml", "<project />\n")
    _write(tmp_path / "service" / "App.csproj", "<Project />\n")
    _write(tmp_path / "coverage.xml", "<coverage />\n")

    payload = discover_adoption_surface(tmp_path)

    assert {"go", "rust", "java", "dotnet"} <= _names(payload["detected_languages"])
    assert {"go_modules", "cargo", "maven", "nuget"} <= _names(payload["package_managers"])
    assert "go test ./..." in _commands(payload)
    assert "cargo test" in _commands(payload)
    assert "mvn test" in _commands(payload)
    assert "dotnet test" in _commands(payload)
    assert payload["artifact_surfaces"] == [{"name": "coverage", "paths": ["coverage.xml"]}]


def test_adoption_surface_module_writes_deterministic_artifact(
    tmp_path: Path,
    capsys,
) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    out = tmp_path / "build" / "sdetkit" / "adoption-surface.json"

    from sdetkit.adoption_surface import main

    rc = main(["--root", str(tmp_path), "--out", str(out), "--format", "json"])

    assert rc == 0
    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert stdout["adoption_surface_json"] == out.as_posix()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_surface_cli_dispatch_writes_artifact(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    out = tmp_path / "adoption-surface.json"

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "adoption-surface",
            "--root",
            str(tmp_path),
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
