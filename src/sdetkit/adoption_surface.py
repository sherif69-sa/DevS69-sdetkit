from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adoption_surface.v1"

IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "site",
}


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _file(root: Path, path: str) -> bool:
    return (root / path).is_file()


def _dir(root: Path, path: str) -> bool:
    return (root / path).is_dir()


def _glob_files(root: Path, pattern: str) -> list[str]:
    return sorted(_rel(root, path) for path in root.glob(pattern) if path.is_file())


def _recursive_files(root: Path, pattern: str) -> list[str]:
    files: list[str] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        if any(part in IGNORED_PARTS for part in path.relative_to(root).parts):
            continue
        files.append(_rel(root, path))
    return sorted(files)


def _read_text(root: Path, path: str) -> str:
    try:
        return (root / path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _read_json(root: Path, path: str) -> dict[str, Any]:
    try:
        payload = json.loads((root / path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _add_named(items: list[dict[str, Any]], name: str, **fields: Any) -> None:
    if any(item.get("name") == name for item in items):
        return
    items.append({"name": name, **fields})


def _workflow_files(root: Path) -> list[str]:
    return _glob_files(root, ".github/workflows/*.yml") + _glob_files(
        root, ".github/workflows/*.yaml"
    )


def _workflow_text(root: Path, files: list[str]) -> str:
    return "\n".join(_read_text(root, path).lower() for path in files)


def _package_json_has_test(root: Path) -> bool:
    payload = _read_json(root, "package.json")
    scripts = payload.get("scripts")
    if not isinstance(scripts, dict):
        return False
    return bool(str(scripts.get("test", "")).strip())


def discover_adoption_surface(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root)
    requirements = _glob_files(root, "requirements*.txt")
    workflows = _workflow_files(root)
    workflow_text = _workflow_text(root, workflows)

    detected_languages: list[dict[str, Any]] = []
    package_managers: list[dict[str, Any]] = []
    test_runners: list[dict[str, Any]] = []
    ci_systems: list[dict[str, Any]] = []
    security_tools: list[dict[str, Any]] = []
    artifact_surfaces: list[dict[str, Any]] = []
    recommended_proof_commands: list[dict[str, Any]] = []
    review_first_unknowns: list[str] = []

    python_evidence = [
        path for path in ["pyproject.toml", "setup.cfg", "setup.py"] if _file(root, path)
    ]
    python_evidence.extend(requirements)
    if _dir(root, "src"):
        python_evidence.append("src/")
    if python_evidence:
        _add_named(
            detected_languages,
            "python",
            confidence="high",
            evidence=sorted(set(python_evidence)),
        )

    if requirements:
        _add_named(package_managers, "pip", files=requirements)
    if _file(root, "uv.lock"):
        _add_named(package_managers, "uv", files=["uv.lock"])
    if _file(root, "poetry.lock"):
        _add_named(package_managers, "poetry", files=["poetry.lock"])

    python_tool_text = "\n".join(
        _read_text(root, path)
        for path in ["pyproject.toml", *requirements]
        if (root / path).is_file()
    ).lower()
    if python_evidence and "pytest" in python_tool_text:
        _add_named(
            test_runners,
            "pytest",
            confidence="high",
            commands=["python -m pytest -q -o addopts="],
        )
        recommended_proof_commands.append(
            {
                "surface": "python",
                "command": "python -m pytest -q -o addopts=",
                "confidence": "high",
            }
        )
    elif python_evidence:
        review_first_unknowns.append("Python project detected but test command is not proven")

    if _file(root, ".pre-commit-config.yaml"):
        recommended_proof_commands.append(
            {
                "surface": "quality",
                "command": "python -m pre_commit run -a",
                "confidence": "high",
            }
        )

    if _file(root, "mkdocs.yml"):
        recommended_proof_commands.append(
            {
                "surface": "docs",
                "command": "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict",
                "confidence": "high",
            }
        )

    js_evidence = [
        path
        for path in [
            "package.json",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "tsconfig.json",
        ]
        if _file(root, path)
    ]
    if js_evidence:
        _add_named(
            detected_languages,
            "javascript_typescript",
            confidence="medium",
            evidence=js_evidence,
        )
    if _file(root, "package-lock.json"):
        _add_named(package_managers, "npm", files=["package-lock.json"])
    if _file(root, "pnpm-lock.yaml"):
        _add_named(package_managers, "pnpm", files=["pnpm-lock.yaml"])
    if _file(root, "yarn.lock"):
        _add_named(package_managers, "yarn", files=["yarn.lock"])
    if _file(root, "package.json") and _package_json_has_test(root):
        _add_named(
            test_runners,
            "node_test_script",
            confidence="medium",
            commands=["npm test"],
        )
        recommended_proof_commands.append(
            {"surface": "javascript_typescript", "command": "npm test", "confidence": "medium"}
        )
    elif _file(root, "package.json"):
        review_first_unknowns.append(
            "JavaScript/TypeScript package manifest detected but test command is not proven"
        )

    if _file(root, "go.mod"):
        _add_named(detected_languages, "go", confidence="high", evidence=["go.mod"])
        _add_named(package_managers, "go_modules", files=["go.mod"])
        recommended_proof_commands.append(
            {"surface": "go", "command": "go test ./...", "confidence": "high"}
        )

    if _file(root, "Cargo.toml"):
        rust_files = [path for path in ["Cargo.toml", "Cargo.lock"] if _file(root, path)]
        _add_named(detected_languages, "rust", confidence="high", evidence=rust_files)
        _add_named(package_managers, "cargo", files=rust_files)
        recommended_proof_commands.append(
            {"surface": "rust", "command": "cargo test", "confidence": "high"}
        )

    java_files = [
        path
        for path in ["pom.xml", "build.gradle", "build.gradle.kts", "gradlew"]
        if _file(root, path)
    ]
    if java_files:
        _add_named(detected_languages, "java", confidence="high", evidence=java_files)
        if _file(root, "pom.xml"):
            _add_named(package_managers, "maven", files=["pom.xml"])
            recommended_proof_commands.append(
                {"surface": "java", "command": "mvn test", "confidence": "high"}
            )
        if _file(root, "build.gradle") or _file(root, "build.gradle.kts"):
            _add_named(package_managers, "gradle", files=java_files)
            recommended_proof_commands.append(
                {"surface": "java", "command": "./gradlew test", "confidence": "medium"}
            )

    dotnet_files = _recursive_files(root, "*.sln") + _recursive_files(root, "*.csproj")
    if dotnet_files:
        _add_named(detected_languages, "dotnet", confidence="high", evidence=dotnet_files)
        _add_named(package_managers, "nuget", files=dotnet_files)
        recommended_proof_commands.append(
            {"surface": "dotnet", "command": "dotnet test", "confidence": "high"}
        )

    if workflows:
        _add_named(ci_systems, "github_actions", files=workflows)
    if _file(root, ".gitlab-ci.yml"):
        _add_named(ci_systems, "gitlab_ci", files=[".gitlab-ci.yml"])
    if _file(root, "Jenkinsfile"):
        _add_named(ci_systems, "jenkins", files=["Jenkinsfile"])

    if "codeql" in workflow_text:
        _add_named(security_tools, "codeql", confidence="detected", evidence=workflows)
    if "dependency-review" in workflow_text:
        _add_named(
            security_tools,
            "dependency_review",
            confidence="detected",
            evidence=workflows,
        )
    if "pip-audit" in workflow_text or "pip-audit" in python_tool_text:
        _add_named(security_tools, "pip_audit", confidence="detected", evidence=workflows)

    if _file(root, "coverage.xml"):
        _add_named(artifact_surfaces, "coverage", paths=["coverage.xml"])
    if _dir(root, "dist"):
        _add_named(artifact_surfaces, "python_distribution", paths=["dist/"])
    if _dir(root, "build"):
        _add_named(artifact_surfaces, "build_output", paths=["build/"])

    return {
        "schema_version": SCHEMA_VERSION,
        "repo_root": ".",
        "detected_languages": sorted(detected_languages, key=lambda item: item["name"]),
        "package_managers": sorted(package_managers, key=lambda item: item["name"]),
        "test_runners": sorted(test_runners, key=lambda item: item["name"]),
        "ci_systems": sorted(ci_systems, key=lambda item: item["name"]),
        "security_tools": sorted(security_tools, key=lambda item: item["name"]),
        "artifact_surfaces": sorted(artifact_surfaces, key=lambda item: item["name"]),
        "recommended_proof_commands": sorted(
            recommended_proof_commands,
            key=lambda item: (item["surface"], item["command"]),
        ),
        "review_first_unknowns": sorted(set(review_first_unknowns)),
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
