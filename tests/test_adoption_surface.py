from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.adoption_surface import SCHEMA_VERSION, discover_adoption_surface


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _names(items: list[dict]) -> set[str]:
    return {str(item["name"]) for item in items}


def _commands(payload: dict) -> set[str]:
    return {str(item["command"]) for item in payload["recommended_proof_commands"]}


def _proof_command(payload: dict, command: str) -> dict:
    commands = {str(item["command"]): item for item in payload["recommended_proof_commands"]}
    return commands[command]


@pytest.mark.parametrize(
    ("files", "expected_manager", "expected_evidence"),
    [
        ({"uv.lock": ""}, "uv", {"uv.lock"}),
        ({"poetry.lock": ""}, "poetry", {"poetry.lock"}),
        ({"pnpm-lock.yaml": "lockfileVersion: '9.0'\n"}, "pnpm", {"pnpm-lock.yaml"}),
        ({"yarn.lock": "# yarn lockfile\n"}, "yarn", {"yarn.lock"}),
        (
            {
                "build.gradle.kts": "plugins { java }\n",
                "gradlew": "#!/usr/bin/env sh\n",
            },
            "gradle",
            {"build.gradle.kts", "gradlew"},
        ),
    ],
)
def test_adoption_surface_detects_remaining_package_manager_markers(
    tmp_path: Path,
    files: dict[str, str],
    expected_manager: str,
    expected_evidence: set[str],
) -> None:
    for relative_path, content in files.items():
        _write(tmp_path / relative_path, content)

    payload = discover_adoption_surface(tmp_path)
    managers = {str(item["name"]): item for item in payload["package_managers"]}

    assert expected_manager in managers
    assert set(managers[expected_manager]["files"]) == expected_evidence
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


@pytest.mark.parametrize(
    ("relative_path", "content"),
    [
        ("pyproject.toml", "[project]\nname = 'manifest-only'\n"),
        ("package.json", '{"name": "manifest-only"}\n'),
    ],
)
def test_adoption_surface_does_not_guess_package_manager_from_manifest_alone(
    tmp_path: Path,
    relative_path: str,
    content: str,
) -> None:
    _write(tmp_path / relative_path, content)

    payload = discover_adoption_surface(tmp_path)

    assert payload["package_managers"] == []
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_surface_detects_python_github_security_and_proof_commands(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    _write(tmp_path / ".pre-commit-config.yaml", "repos: []\n")
    _write(
        tmp_path / "Makefile",
        ".PHONY: proof-after-format\nproof-after-format:\n\tpython -m pre_commit run -a\n",
    )
    _write(tmp_path / "mkdocs.yml", "site_name: Example\n")
    _write(tmp_path / "src" / "sdetkit" / "__init__.py")
    _write(
        tmp_path / ".github" / "workflows" / "security.yml",
        "steps:\n  - uses: github/codeql-action/init@abc\n  - uses: actions/dependency-review-action@abc\n",
    )

    payload = discover_adoption_surface(tmp_path)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert "python" in _names(payload["detected_languages"])
    assert "pip" in _names(payload["package_managers"])
    assert "pytest" in _names(payload["test_runners"])
    assert "github_actions" in _names(payload["ci_systems"])
    assert {"codeql", "dependency_review"} <= _names(payload["security_tools"])
    assert "python -m pytest -q -o addopts=" in _commands(payload)
    assert "make proof-after-format" in _commands(payload)
    assert "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict" in _commands(payload)
    assert _proof_command(payload, "python -m pytest -q -o addopts=")["purpose"] == "test"
    assert _proof_command(payload, "make proof-after-format")["purpose"] == "quality"
    assert (
        _proof_command(payload, "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict")["purpose"]
        == "docs"
    )


@pytest.mark.parametrize(
    ("python_file", "python_content", "expected_pip_audit_evidence"),
    [
        (
            "pyproject.toml",
            "[project.optional-dependencies]\nsecurity = ['pip-audit']\n",
            {"pyproject.toml"},
        ),
        (
            "requirements-security.txt",
            "pip-audit==2.9.0\n",
            {"requirements-security.txt"},
        ),
    ],
)
def test_adoption_surface_security_tool_evidence_is_source_specific(
    tmp_path: Path,
    python_file: str,
    python_content: str,
    expected_pip_audit_evidence: set[str],
) -> None:
    _write(tmp_path / python_file, python_content)
    _write(
        tmp_path / ".github" / "workflows" / "codeql.yml",
        "steps:\n  - uses: github/codeql-action/init@abc\n",
    )
    _write(
        tmp_path / ".github" / "workflows" / "dependency-review.yml",
        "steps:\n  - uses: actions/dependency-review-action@abc\n",
    )
    _write(
        tmp_path / ".github" / "workflows" / "unrelated.yml",
        "steps:\n  - run: echo unrelated\n",
    )

    payload = discover_adoption_surface(tmp_path)
    tools = {str(item["name"]): item for item in payload["security_tools"]}

    assert set(tools) == {"codeql", "dependency_review", "pip_audit"}
    assert set(tools["codeql"]["evidence"]) == {".github/workflows/codeql.yml"}
    assert set(tools["dependency_review"]["evidence"]) == {
        ".github/workflows/dependency-review.yml"
    }
    assert set(tools["pip_audit"]["evidence"]) == expected_pip_audit_evidence
    assert ".github/workflows/unrelated.yml" not in {
        evidence for tool in tools.values() for evidence in tool["evidence"]
    }
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_surface_combines_pip_audit_workflow_and_python_evidence(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "pyproject.toml",
        "[project.optional-dependencies]\nsecurity = ['pip-audit']\n",
    )
    _write(
        tmp_path / ".github" / "workflows" / "dependency-audit.yml",
        "steps:\n  - run: python -m pip_audit\n  - run: pip-audit\n",
    )

    payload = discover_adoption_surface(tmp_path)
    tools = {str(item["name"]): item for item in payload["security_tools"]}

    assert set(tools["pip_audit"]["evidence"]) == {
        "pyproject.toml",
        ".github/workflows/dependency-audit.yml",
    }
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


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


def test_adoption_surface_recommended_proof_commands_include_operator_purpose(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    _write(tmp_path / ".pre-commit-config.yaml", "repos: []\n")
    _write(
        tmp_path / "Makefile",
        ".PHONY: proof-after-format\nproof-after-format:\n\tpython -m pre_commit run -a\n",
    )
    _write(tmp_path / "mkdocs.yml", "site_name: Example\n")
    _write(
        tmp_path / "package.json",
        json.dumps({"name": "demo", "scripts": {"test": "vitest"}}),
    )
    _write(tmp_path / "package-lock.json", "{}\n")
    _write(tmp_path / "go.mod", "module example\n")
    _write(tmp_path / "Cargo.toml", "[package]\nname = 'example'\n")
    _write(tmp_path / "pom.xml", "<project />\n")
    _write(tmp_path / "service" / "App.csproj", "<Project />\n")

    payload = discover_adoption_surface(tmp_path)
    commands = payload["recommended_proof_commands"]

    assert commands
    assert all(
        {"surface", "command", "confidence", "purpose"} <= set(command) for command in commands
    )
    assert _proof_command(payload, "python -m pytest -q -o addopts=")["purpose"] == "test"
    assert _proof_command(payload, "make proof-after-format")["purpose"] == "quality"
    assert (
        _proof_command(payload, "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict")["purpose"]
        == "docs"
    )
    assert _proof_command(payload, "npm test")["purpose"] == "test"
    assert _proof_command(payload, "go test ./...")["purpose"] == "test"
    assert _proof_command(payload, "cargo test")["purpose"] == "test"
    assert _proof_command(payload, "mvn test")["purpose"] == "test"
    assert _proof_command(payload, "dotnet test")["purpose"] == "test"


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


def test_adoption_surface_detects_standard_evidence_artifacts(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "reports" / "coverage.xml", "<coverage />\n")
    _write(tmp_path / "reports" / "coverage.json", "{}\n")
    _write(tmp_path / "reports" / "lcov.info", "TN:\n")
    _write(tmp_path / "reports" / "junit.xml", "<testsuite />\n")
    _write(tmp_path / "reports" / "junit-unit.xml", "<testsuite />\n")
    _write(tmp_path / "reports" / "junit_integration.xml", "<testsuite />\n")
    _write(tmp_path / "security" / "security.sarif", "{}\n")
    _write(tmp_path / "security" / "codeql.sarif.json", "{}\n")
    _write(tmp_path / "sbom" / "application.cdx.json", "{}\n")
    _write(tmp_path / "sbom" / "application.spdx.json", "{}\n")
    _write(tmp_path / "sbom" / "sbom.xml", "<bom />\n")

    payload = discover_adoption_surface(tmp_path)
    surfaces = {str(item["name"]): item for item in payload["artifact_surfaces"]}

    assert set(surfaces) == {
        "coverage",
        "junit_xml",
        "sarif",
        "sbom",
    }
    assert surfaces["coverage"]["paths"] == [
        "reports/coverage.json",
        "reports/coverage.xml",
        "reports/lcov.info",
    ]
    assert surfaces["junit_xml"]["paths"] == [
        "reports/junit-unit.xml",
        "reports/junit.xml",
        "reports/junit_integration.xml",
    ]
    assert surfaces["sarif"]["paths"] == [
        "security/codeql.sarif.json",
        "security/security.sarif",
    ]
    assert surfaces["sbom"]["paths"] == [
        "sbom/application.cdx.json",
        "sbom/application.spdx.json",
        "sbom/sbom.xml",
    ]
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_surface_ignores_non_artifacts_and_ignored_tree_artifacts(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "docs" / "example.xml", "<example />\n")
    _write(tmp_path / "data" / "report.json", "{}\n")
    _write(tmp_path / "site" / "junit.xml", "<testsuite />\n")
    _write(tmp_path / "node_modules" / "security.sarif", "{}\n")

    payload = discover_adoption_surface(tmp_path)

    assert payload["artifact_surfaces"] == []
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_surface_profiles_external_repo_readiness_without_authority(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    _write(
        tmp_path / ".git" / "config",
        '[remote "origin"]\n    url = https://token@example.com/org/repo.git\n',
    )

    payload = discover_adoption_surface(tmp_path)

    assert payload["repo_root"] == tmp_path.as_posix()
    assert payload["repo_identity"] == {
        "name": tmp_path.name,
        "is_current_sdetkit_repo": False,
        "git_detected": True,
        "remote_url": "https://example.com/org/repo.git",
    }
    assert payload["operator_summary"] == {
        "status": "read_only_profile_generated",
        "next_action": (
            "Review detected surfaces and manually run trusted proof commands in the target repo."
        ),
    }
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert all(
        command["auto_run_allowed"] is False for command in payload["recommended_proof_commands"]
    )
    assert all(
        command["executes_untrusted_code"] is True
        for command in payload["recommended_proof_commands"]
    )


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
    assert payload["patch_application_allowed"] is False
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


def test_adoption_surface_payload_validator_accepts_generated_payload(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")

    from sdetkit.adoption_surface import (
        validate_adoption_surface_artifact,
        validate_adoption_surface_payload,
        write_adoption_surface_artifact,
    )

    payload = discover_adoption_surface(tmp_path)
    assert validate_adoption_surface_payload(payload) == []

    out = tmp_path / "build" / "sdetkit" / "adoption-surface.json"
    write_adoption_surface_artifact(repo_root=tmp_path, out=out)
    assert validate_adoption_surface_artifact(out) == []


def test_adoption_surface_falls_back_to_pre_commit_when_make_target_is_absent(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "pyproject.toml", "[project]\ndependencies = []\n")
    _write(tmp_path / ".pre-commit-config.yaml", "repos: []\n")

    payload = discover_adoption_surface(tmp_path)

    assert "python -m pre_commit run -a" in _commands(payload)


def test_adoption_surface_payload_validator_rejects_authority_escalation() -> None:
    from sdetkit.adoption_surface import validate_adoption_surface_payload

    payload = {
        "schema_version": SCHEMA_VERSION,
        "detected_languages": [],
        "package_managers": [],
        "test_runners": [],
        "ci_systems": [],
        "security_tools": [],
        "docs_tools": [],
        "release_surfaces": [],
        "artifact_surfaces": [],
        "recommended_proof_commands": [],
        "review_first_unknowns": [],
        "repo_identity": {},
        "operator_summary": {},
        "automation_allowed": True,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }

    assert validate_adoption_surface_payload(payload) == ["automation_allowed must be false"]


def test_adoption_surface_report_renders_operator_readiness_summary(
    tmp_path: Path,
    capsys,
) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    _write(tmp_path / ".pre-commit-config.yaml", "repos: []\n")
    _write(tmp_path / "package.json", json.dumps({"name": "demo", "scripts": {"build": "tsc"}}))
    out = tmp_path / "adoption-surface.json"

    from sdetkit.adoption_surface import main

    rc = main(["--root", str(tmp_path), "--out", str(out), "--format", "report"])

    assert rc == 0
    report = capsys.readouterr().out
    assert "# SDETKit adoption readiness report" in report
    assert "## Detected languages" in report
    assert "- python (high)" in report
    assert "- javascript_typescript (medium)" in report
    assert "## Recommended proof commands" in report
    assert "`python -m pytest -q -o addopts=`" in report
    assert "auto_run_allowed=false" in report
    assert "## Review-first unknowns" in report
    assert (
        "JavaScript/TypeScript package manifest detected but test command is not proven" in report
    )
    assert "## Authority boundary" in report
    assert "- automation_allowed: false" in report
    assert "- patch_application_allowed: false" in report
    assert "- merge_authorized: false" in report
    assert "- semantic_equivalence_proven: false" in report


def test_adoption_surface_cli_dispatch_renders_operator_report(
    tmp_path: Path,
    capsys,
) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    _write(tmp_path / "package.json", json.dumps({"name": "demo", "scripts": {"build": "tsc"}}))
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
            "report",
        ]
    )

    assert rc == 0
    report = capsys.readouterr().out
    assert "# SDETKit adoption readiness report" in report
    assert "## Recommended proof commands" in report
    assert "auto_run_allowed=false" in report
    assert "- patch_application_allowed: false" in report


def test_adoption_surface_detects_docs_and_release_surfaces_without_running_commands(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "mkdocs.yml", "site_name: Example\n")
    _write(tmp_path / "docs" / "index.md", "# Example\n")
    _write(tmp_path / "CHANGELOG.md", "# Changelog\n")
    _write(
        tmp_path / ".github" / "workflows" / "release.yml",
        "name: release\non: workflow_dispatch\njobs:\n  publish:\n    runs-on: ubuntu-latest\n    steps: []\n",
    )

    payload = discover_adoption_surface(tmp_path)

    assert payload["docs_tools"] == [
        {
            "name": "mkdocs",
            "confidence": "high",
            "evidence": ["mkdocs.yml", "docs/"],
        }
    ]
    assert _names(payload["release_surfaces"]) == {"changelog", "release_workflow"}
    assert "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict" in _commands(payload)


def test_adoption_surface_payload_validator_accepts_docs_and_release_surface_lists() -> None:
    from sdetkit.adoption_surface import validate_adoption_surface_payload

    payload = {
        "schema_version": SCHEMA_VERSION,
        "detected_languages": [],
        "package_managers": [],
        "test_runners": [],
        "ci_systems": [],
        "security_tools": [],
        "docs_tools": [],
        "release_surfaces": [],
        "artifact_surfaces": [],
        "recommended_proof_commands": [],
        "review_first_unknowns": [],
        "repo_identity": {},
        "operator_summary": {},
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }

    assert validate_adoption_surface_payload(payload) == []
