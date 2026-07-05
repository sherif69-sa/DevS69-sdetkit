from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adoption_surface.v1"
REQUIRED_LIST_FIELDS = (
    "detected_languages",
    "package_managers",
    "test_runners",
    "ci_systems",
    "security_tools",
    "docs_tools",
    "release_surfaces",
    "artifact_surfaces",
    "recommended_proof_commands",
    "review_first_unknowns",
)
REQUIRED_FALSE_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)
REQUIRED_OBJECT_FIELDS = ("repo_identity", "operator_summary")
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
GITLAB_RESERVED_TOP_LEVEL_KEYS = {
    "after_script",
    "before_script",
    "cache",
    "default",
    "image",
    "include",
    "pages",
    "services",
    "stages",
    "variables",
    "workflow",
}


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _file(root: Path, path: str) -> bool:
    return (root / path).is_file()


def _dir(root: Path, path: str) -> bool:
    return (root / path).is_dir()


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


def _recursive_files_for_patterns(root: Path, patterns: Sequence[str]) -> list[str]:
    return sorted({path for pattern in patterns for path in _recursive_files(root, pattern)})


def _add_named(items: list[dict[str, Any]], name: str, **fields: Any) -> None:
    if not any(item.get("name") == name for item in items):
        items.append({"name": name, **fields})


def _add_proof_command(
    items: list[dict[str, Any]],
    *,
    surface: str,
    command: str,
    confidence: str,
    purpose: str,
    evidence: Sequence[str] | None = None,
    source: dict[str, Any] | None = None,
) -> None:
    item: dict[str, Any] = {
        "surface": surface,
        "command": command,
        "confidence": confidence,
        "purpose": purpose,
        "executes_untrusted_code": True,
        "auto_run_allowed": False,
    }
    if evidence:
        item["evidence"] = list(evidence)
    if source:
        item["source"] = dict(source)
    if not any(
        existing.get("surface") == surface and existing.get("command") == command
        for existing in items
    ):
        items.append(item)


def _workflow_files(root: Path) -> list[str]:
    return _glob_files(root, ".github/workflows/*.yml") + _glob_files(
        root, ".github/workflows/*.yaml"
    )


def _owned_script_files(root: Path) -> list[str]:
    named = [
        path
        for path in ("Makefile", "Taskfile.yml", "Taskfile.yaml", "justfile", "Justfile")
        if _file(root, path)
    ]
    return sorted(set(named + _recursive_files(root, "*.sh")))


def _files_containing(root: Path, files: Sequence[str], needle: str) -> list[str]:
    normalized = needle.lower()
    return sorted(path for path in files if normalized in _read_text(root, path).lower())


def _package_json_has_test(root: Path) -> bool:
    scripts = _read_json(root, "package.json").get("scripts")
    return isinstance(scripts, dict) and bool(str(scripts.get("test", "")).strip())


def _javascript_test_command(root: Path) -> str:
    if _file(root, "pnpm-lock.yaml"):
        return "pnpm test"
    if _file(root, "yarn.lock"):
        return "yarn test"
    return "npm test"


def _make_target_exists(root: Path, target: str) -> bool:
    return _file(root, "Makefile") and any(
        line.startswith(f"{target}:") for line in _read_text(root, "Makefile").splitlines()
    )


def _quality_proof_command(root: Path) -> str:
    return (
        "make proof-after-format"
        if _make_target_exists(root, "proof-after-format")
        else "python -m pre_commit run -a"
    )


def _tox_config_evidence(root: Path) -> list[str]:
    evidence = ["tox.ini"] if _file(root, "tox.ini") else []
    if any(
        line.strip() == "[tool.tox]" for line in _read_text(root, "pyproject.toml").splitlines()
    ):
        evidence.append("pyproject.toml")
    return evidence


def _sanitize_remote_url(url: str) -> str:
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    return f"{scheme}://{rest.rsplit('@', 1)[-1]}"


def _git_remote_url(root: Path) -> str:
    config = root / ".git" / "config"
    if not config.is_file():
        return ""
    in_origin = False
    for raw_line in config.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if line.startswith("[remote "):
            in_origin = '"origin"' in line or "'origin'" in line
            continue
        if in_origin and line.startswith("url ="):
            return _sanitize_remote_url(line.split("=", 1)[1].strip())
    return ""


def _repo_identity(root: Path) -> dict[str, Any]:
    try:
        is_current = root.resolve() == Path.cwd().resolve()
    except OSError:
        is_current = False
    return {
        "name": root.resolve().name if root.exists() else root.name,
        "is_current_sdetkit_repo": is_current,
        "git_detected": (root / ".git").exists(),
        "remote_url": _git_remote_url(root),
    }


def _operator_summary() -> dict[str, str]:
    return {
        "status": "read_only_profile_generated",
        "next_action": "Review detected surfaces and manually run trusted proof commands in the target repo.",
    }


def _top_level_yaml_key(raw_line: str) -> tuple[str, str] | None:
    if not raw_line or raw_line.startswith((" ", "\t")):
        return None
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#") or ":" not in stripped:
        return None
    key, value = stripped.split(":", 1)
    return (key.strip(), value.strip()) if key.strip() else None


def _strip_literal(value: str) -> str:
    value = value.strip().rstrip(",")
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _literal_gitlab_script_values(value: str) -> tuple[list[str], bool]:
    value = value.strip()
    if not value:
        return [], False
    if value in {"|", ">", "|-", ">-", "|+", ">+"}:
        return [], True
    if value.startswith("["):
        try:
            parsed = json.loads(value.replace("'", '"'))
        except json.JSONDecodeError:
            return [], True
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            return [], True
        return [item.strip() for item in parsed if item.strip()], False
    return [_strip_literal(value)], False


def _command_is_dynamic(command: str) -> bool:
    return any(token in command for token in ("$", "`", "*", "&"))


def _command_is_shell_message(command: str) -> bool:
    return command.lstrip().lower().startswith("echo ")


def _classify_proof_purpose(command: str) -> str:
    normalized = command.lower()
    if any(
        needle in normalized
        for needle in (
            "pip-audit",
            "pip_audit",
            "npm audit",
            "cargo audit",
            "govulncheck",
            "bandit",
            "safety check",
            "trivy",
            "semgrep",
            "codeql",
        )
    ):
        return "security"
    if any(
        needle in normalized for needle in ("mypy", "pyright", "tsc", "typecheck", "type-check")
    ):
        return "type"
    if any(
        needle in normalized
        for needle in ("ruff", "flake8", "eslint", "pylint", "golangci-lint", "clippy")
    ):
        return "lint"
    if any(
        needle in normalized
        for needle in (
            "pytest",
            "npm test",
            "pnpm test",
            "yarn test",
            "go test",
            "cargo test",
            "mvn test",
            "gradle test",
            "./gradlew test",
            "dotnet test",
            "vitest",
            "jest",
        )
    ):
        return "test"
    if any(needle in normalized for needle in ("mkdocs", "sphinx", "docs")):
        return "docs"
    return "unknown"


def _iter_gitlab_jobs(text: str) -> list[tuple[str, list[str]]]:
    jobs: list[tuple[str, list[str]]] = []
    current_name = ""
    current_block: list[str] = []
    for raw_line in text.splitlines():
        parsed = _top_level_yaml_key(raw_line)
        if parsed is not None:
            if current_name:
                jobs.append((current_name, current_block))
            current_name = parsed[0]
            current_block = [raw_line]
            continue
        if current_name:
            current_block.append(raw_line)
    if current_name:
        jobs.append((current_name, current_block))
    return jobs


def _extract_gitlab_job_script_commands(
    job_name: str, block: list[str]
) -> tuple[list[str], list[str]]:
    commands: list[str] = []
    unknowns: list[str] = []
    in_script = False
    script_indent = 0
    for raw_line in block[1:]:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if stripped.startswith(("extends:", "rules:", "needs:")):
            unknowns.append(
                f"GitLab CI job {job_name} uses dynamic or inherited behavior that was not resolved"
            )
        if in_script and indent <= script_indent and not stripped.startswith("-"):
            in_script = False
        if in_script:
            if stripped.startswith("-"):
                values, unresolved = _literal_gitlab_script_values(stripped[1:].strip())
                if unresolved:
                    unknowns.append(
                        f"GitLab CI job {job_name} has unresolved script content that was not guessed"
                    )
                    continue
                for command in values:
                    if _command_is_shell_message(command):
                        continue
                    if _command_is_dynamic(command):
                        unknowns.append(
                            f"GitLab CI job {job_name} has dynamic script command that was not guessed"
                        )
                    else:
                        commands.append(command)
                continue
            if stripped in {"|", ">", "|-", ">-", "|+", ">+"}:
                unknowns.append(
                    f"GitLab CI job {job_name} has multiline script content that was not guessed"
                )
            continue
        if stripped.startswith("script:"):
            rest = stripped.split(":", 1)[1].strip()
            if not rest:
                in_script = True
                script_indent = indent
                continue
            values, unresolved = _literal_gitlab_script_values(rest)
            if unresolved:
                unknowns.append(
                    f"GitLab CI job {job_name} has unresolved script content that was not guessed"
                )
                continue
            for command in values:
                if _command_is_shell_message(command):
                    continue
                if _command_is_dynamic(command):
                    unknowns.append(
                        f"GitLab CI job {job_name} has dynamic script command that was not guessed"
                    )
                else:
                    commands.append(command)
    return commands, unknowns


def _extract_gitlab_ci_commands(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = ".gitlab-ci.yml"
    text = _read_text(root, path)
    if not text:
        return [], []
    extracted: list[dict[str, Any]] = []
    unknowns: list[str] = []
    for raw_line in text.splitlines():
        parsed = _top_level_yaml_key(raw_line)
        if parsed is not None and parsed[0] == "include":
            unknowns.append("GitLab CI include detected; remote configuration was not resolved")
    for job_name, block in _iter_gitlab_jobs(text):
        normalized = job_name.strip()
        if (
            not normalized
            or normalized.startswith(".")
            or normalized in GITLAB_RESERVED_TOP_LEVEL_KEYS
        ):
            continue
        if any("&" in line or "*" in line for line in block):
            unknowns.append(
                f"GitLab CI job {normalized} uses YAML anchor or alias content that was not resolved"
            )
            continue
        commands, job_unknowns = _extract_gitlab_job_script_commands(normalized, block)
        unknowns.extend(job_unknowns)
        for command in commands:
            extracted.append(
                {
                    "command": command,
                    "purpose": _classify_proof_purpose(command),
                    "job": normalized,
                    "file": path,
                }
            )
    return extracted, sorted(set(unknowns))


def discover_adoption_surface(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root)
    requirements = _glob_files(root, "requirements*.txt")
    workflows = _workflow_files(root)
    script_files = _owned_script_files(root)
    detected_languages: list[dict[str, Any]] = []
    package_managers: list[dict[str, Any]] = []
    test_runners: list[dict[str, Any]] = []
    ci_systems: list[dict[str, Any]] = []
    security_tools: list[dict[str, Any]] = []
    docs_tools: list[dict[str, Any]] = []
    release_surfaces: list[dict[str, Any]] = []
    artifact_surfaces: list[dict[str, Any]] = []
    recommended_proof_commands: list[dict[str, Any]] = []
    review_first_unknowns: list[str] = []

    tox_evidence = _tox_config_evidence(root)
    python_evidence = [
        path for path in ("pyproject.toml", "setup.cfg", "setup.py") if _file(root, path)
    ]
    python_evidence.extend(requirements)
    python_evidence.extend(tox_evidence)
    if _dir(root, "src"):
        python_evidence.append("src/")
    if python_evidence:
        _add_named(
            detected_languages, "python", confidence="high", evidence=sorted(set(python_evidence))
        )
    if requirements:
        _add_named(package_managers, "pip", files=requirements)
    if _file(root, "uv.lock"):
        _add_named(package_managers, "uv", files=["uv.lock"])
    if _file(root, "poetry.lock"):
        _add_named(package_managers, "poetry", files=["poetry.lock"])
    python_text = "\n".join(
        _read_text(root, path)
        for path in ["pyproject.toml", *requirements]
        if (root / path).is_file()
    ).lower()
    if python_evidence and "pytest" in python_text:
        _add_named(
            test_runners, "pytest", confidence="high", commands=["python -m pytest -q -o addopts="]
        )
        _add_proof_command(
            recommended_proof_commands,
            surface="python",
            command="python -m pytest -q -o addopts=",
            confidence="high",
            purpose="test",
        )
    elif python_evidence and not tox_evidence:
        review_first_unknowns.append("Python project detected but test command is not proven")
    if tox_evidence:
        _add_proof_command(
            recommended_proof_commands,
            surface="python",
            command="python -m tox",
            confidence="high",
            purpose="test",
        )
    if _file(root, ".pre-commit-config.yaml"):
        _add_proof_command(
            recommended_proof_commands,
            surface="quality",
            command=_quality_proof_command(root),
            confidence="high",
            purpose="quality",
        )
    if _file(root, "docs/conf.py"):
        _add_named(docs_tools, "sphinx", confidence="high", evidence=["docs/conf.py"])
        _add_proof_command(
            recommended_proof_commands,
            surface="docs",
            command="python -m sphinx -W -b html docs docs/_build/html",
            confidence="high",
            purpose="docs",
        )
    if _file(root, "mkdocs.yml"):
        _add_named(
            docs_tools,
            "mkdocs",
            confidence="high",
            evidence=["mkdocs.yml", *(["docs/"] if _dir(root, "docs") else [])],
        )
        _add_proof_command(
            recommended_proof_commands,
            surface="docs",
            command="NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict",
            confidence="high",
            purpose="docs",
        )
    elif _dir(root, "docs") and not _file(root, "docs/conf.py"):
        _add_named(docs_tools, "docs_directory", confidence="medium", evidence=["docs/"])

    js_evidence = [
        path
        for path in (
            "package.json",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "tsconfig.json",
        )
        if _file(root, path)
    ]
    if js_evidence:
        _add_named(
            detected_languages, "javascript_typescript", confidence="medium", evidence=js_evidence
        )
    if _file(root, "package-lock.json"):
        _add_named(package_managers, "npm", files=["package-lock.json"])
    if _file(root, "pnpm-lock.yaml"):
        _add_named(package_managers, "pnpm", files=["pnpm-lock.yaml"])
    if _file(root, "yarn.lock"):
        _add_named(package_managers, "yarn", files=["yarn.lock"])
    if _file(root, "package.json") and _package_json_has_test(root):
        node_command = _javascript_test_command(root)
        _add_named(test_runners, "node_test_script", confidence="medium", commands=[node_command])
        _add_proof_command(
            recommended_proof_commands,
            surface="javascript_typescript",
            command=node_command,
            confidence="medium",
            purpose="test",
        )
    elif _file(root, "package.json"):
        review_first_unknowns.append(
            "JavaScript/TypeScript package manifest detected but test command is not proven"
        )

    if _file(root, "go.mod"):
        _add_named(detected_languages, "go", confidence="high", evidence=["go.mod"])
        _add_named(package_managers, "go_modules", files=["go.mod"])
        _add_proof_command(
            recommended_proof_commands,
            surface="go",
            command="go test ./...",
            confidence="high",
            purpose="test",
        )
    if _file(root, "Cargo.toml"):
        rust_files = [path for path in ("Cargo.toml", "Cargo.lock") if _file(root, path)]
        _add_named(detected_languages, "rust", confidence="high", evidence=rust_files)
        _add_named(package_managers, "cargo", files=rust_files)
        _add_proof_command(
            recommended_proof_commands,
            surface="rust",
            command="cargo test",
            confidence="high",
            purpose="test",
        )
    java_files = [
        path
        for path in ("pom.xml", "build.gradle", "build.gradle.kts", "gradlew")
        if _file(root, path)
    ]
    if java_files:
        _add_named(detected_languages, "java", confidence="high", evidence=java_files)
    if _file(root, "pom.xml"):
        _add_named(package_managers, "maven", files=["pom.xml"])
        _add_proof_command(
            recommended_proof_commands,
            surface="java",
            command="mvn test",
            confidence="high",
            purpose="test",
        )
    if _file(root, "build.gradle") or _file(root, "build.gradle.kts"):
        _add_named(package_managers, "gradle", files=java_files)
        has_wrapper = _file(root, "gradlew")
        _add_proof_command(
            recommended_proof_commands,
            surface="java",
            command="./gradlew test" if has_wrapper else "gradle test",
            confidence="high" if has_wrapper else "medium",
            purpose="test",
        )
    dotnet_files = _recursive_files(root, "*.sln") + _recursive_files(root, "*.csproj")
    if dotnet_files:
        _add_named(detected_languages, "dotnet", confidence="high", evidence=dotnet_files)
        _add_named(package_managers, "nuget", files=dotnet_files)
        _add_proof_command(
            recommended_proof_commands,
            surface="dotnet",
            command="dotnet test",
            confidence="high",
            purpose="test",
        )

    if workflows:
        _add_named(ci_systems, "github_actions", files=workflows)
    if _file(root, ".gitlab-ci.yml"):
        _add_named(ci_systems, "gitlab_ci", files=[".gitlab-ci.yml"])
        gitlab_commands, gitlab_unknowns = _extract_gitlab_ci_commands(root)
        review_first_unknowns.extend(gitlab_unknowns)
        for command in gitlab_commands:
            _add_proof_command(
                recommended_proof_commands,
                surface="gitlab_ci",
                command=str(command["command"]),
                confidence="medium",
                purpose=str(command["purpose"]),
                evidence=[str(command["file"])],
                source={
                    "ci_system": "gitlab_ci",
                    "file": str(command["file"]),
                    "job": str(command["job"]),
                },
            )
    if _file(root, "Jenkinsfile"):
        _add_named(ci_systems, "jenkins", files=["Jenkinsfile"])

    codeql_evidence = _files_containing(root, workflows, "codeql")
    if codeql_evidence:
        _add_named(security_tools, "codeql", confidence="detected", evidence=codeql_evidence)
    dependency_evidence = _files_containing(root, workflows, "dependency-review")
    if dependency_evidence:
        _add_named(
            security_tools, "dependency_review", confidence="detected", evidence=dependency_evidence
        )
    python_tool_files = [
        path for path in ["pyproject.toml", *requirements] if (root / path).is_file()
    ]
    pip_audit_evidence = sorted(
        set(
            _files_containing(root, workflows, "pip-audit")
            + _files_containing(root, python_tool_files, "pip-audit")
        )
    )
    if pip_audit_evidence:
        _add_named(security_tools, "pip_audit", confidence="detected", evidence=pip_audit_evidence)
    govulncheck_evidence = sorted(
        set(
            _files_containing(root, workflows, "govulncheck")
            + _files_containing(root, script_files, "govulncheck")
        )
    )
    if _file(root, "go.mod") and govulncheck_evidence:
        _add_named(
            security_tools, "govulncheck", confidence="detected", evidence=govulncheck_evidence
        )
        _add_proof_command(
            recommended_proof_commands,
            surface="go",
            command="govulncheck ./...",
            confidence="medium",
            purpose="security",
        )

    release_workflows = [
        path
        for path in workflows
        if "release" in Path(path).name.lower()
        or "publish" in Path(path).name.lower()
        or "release" in _read_text(root, path).lower()
        or "publish" in _read_text(root, path).lower()
    ]
    if release_workflows:
        _add_named(
            release_surfaces, "release_workflow", confidence="detected", evidence=release_workflows
        )
    if _file(root, "CHANGELOG.md"):
        _add_named(release_surfaces, "changelog", confidence="detected", evidence=["CHANGELOG.md"])
    for name, patterns in {
        "coverage": ("coverage.xml", "coverage.json", "lcov.info"),
        "junit_xml": ("junit.xml", "junit-*.xml", "junit_*.xml"),
        "sarif": ("*.sarif", "*.sarif.json"),
        "sbom": ("*.cdx.json", "*.spdx.json", "sbom.json", "sbom.xml", "bom.json", "bom.xml"),
    }.items():
        paths = _recursive_files_for_patterns(root, patterns)
        if paths:
            _add_named(artifact_surfaces, name, paths=paths)
    if _dir(root, "dist"):
        _add_named(artifact_surfaces, "python_distribution", paths=["dist/"])
    if _dir(root, "build"):
        _add_named(artifact_surfaces, "build_output", paths=["build/"])
    return {
        "schema_version": SCHEMA_VERSION,
        "repo_root": root.as_posix(),
        "repo_identity": _repo_identity(root),
        "detected_languages": sorted(detected_languages, key=lambda item: item["name"]),
        "package_managers": sorted(package_managers, key=lambda item: item["name"]),
        "test_runners": sorted(test_runners, key=lambda item: item["name"]),
        "ci_systems": sorted(ci_systems, key=lambda item: item["name"]),
        "security_tools": sorted(security_tools, key=lambda item: item["name"]),
        "docs_tools": sorted(docs_tools, key=lambda item: item["name"]),
        "release_surfaces": sorted(release_surfaces, key=lambda item: item["name"]),
        "artifact_surfaces": sorted(artifact_surfaces, key=lambda item: item["name"]),
        "recommended_proof_commands": sorted(
            recommended_proof_commands, key=lambda item: (item["surface"], item["command"])
        ),
        "review_first_unknowns": sorted(set(review_first_unknowns)),
        "operator_summary": _operator_summary(),
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _format_named_items(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["- none detected"]
    lines = []
    for item in items:
        if isinstance(item, dict):
            suffix = f" ({item['confidence']})" if item.get("confidence") else ""
            lines.append(f"- {item.get('name', 'unknown')}{suffix}")
    return lines or ["- none detected"]


def _format_proof_commands(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["- none recommended"]
    lines = []
    for item in items:
        if isinstance(item, dict) and str(item.get("command", "")).strip():
            lines.append(
                f"- `{item['command']}` - surface={item.get('surface', 'unknown')}; purpose={item.get('purpose', 'unknown')}; auto_run_allowed={str(item.get('auto_run_allowed', False)).lower()}"
            )
    return lines or ["- none recommended"]


def render_adoption_surface_report(payload: dict[str, Any]) -> str:
    identity = (
        payload.get("repo_identity") if isinstance(payload.get("repo_identity"), dict) else {}
    )
    summary = (
        payload.get("operator_summary") if isinstance(payload.get("operator_summary"), dict) else {}
    )
    lines = [
        "# SDETKit adoption readiness report",
        "",
        "## Repository",
        f"- name: {identity.get('name', 'unknown')}",
        f"- git_detected: {str(identity.get('git_detected', False)).lower()}",
        f"- is_current_sdetkit_repo: {str(identity.get('is_current_sdetkit_repo', False)).lower()}",
        f"- remote_url: {identity.get('remote_url', '')}",
        "",
        "## Detected languages",
        *_format_named_items(payload.get("detected_languages")),
        "",
        "## Package managers",
        *_format_named_items(payload.get("package_managers")),
        "",
        "## Test runners",
        *_format_named_items(payload.get("test_runners")),
        "",
        "## CI systems",
        *_format_named_items(payload.get("ci_systems")),
        "",
        "## Security tools",
        *_format_named_items(payload.get("security_tools")),
        "",
        "## Docs tools",
        *_format_named_items(payload.get("docs_tools")),
        "",
        "## Release surfaces",
        *_format_named_items(payload.get("release_surfaces")),
        "",
        "## Recommended proof commands",
        *_format_proof_commands(payload.get("recommended_proof_commands")),
        "",
        "## Review-first unknowns",
        *(
            [f"- {item}" for item in payload.get("review_first_unknowns", [])]
            if payload.get("review_first_unknowns")
            else ["- none"]
        ),
        "",
        "## Operator summary",
        f"- status: {summary.get('status', 'unknown')}",
        f"- next_action: {summary.get('next_action', '')}",
        "",
        "## Authority boundary",
        f"- automation_allowed: {str(payload.get('automation_allowed', True)).lower()}",
        f"- patch_application_allowed: {str(payload.get('patch_application_allowed', True)).lower()}",
        f"- merge_authorized: {str(payload.get('merge_authorized', True)).lower()}",
        f"- semantic_equivalence_proven: {str(payload.get('semantic_equivalence_proven', True)).lower()}",
        "",
    ]
    return "\n".join(lines)


def write_adoption_surface_artifact(
    *, repo_root: str | Path = ".", out: str | Path = "build/sdetkit/adoption-surface.json"
) -> dict[str, Any]:
    payload = discover_adoption_surface(repo_root)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema_version": payload["schema_version"],
        "adoption_surface_json": out_path.as_posix(),
        "automation_allowed": payload["automation_allowed"],
        "patch_application_allowed": payload["patch_application_allowed"],
        "merge_authorized": payload["merge_authorized"],
        "semantic_equivalence_proven": payload["semantic_equivalence_proven"],
    }


def validate_adoption_surface_payload(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]
    errors = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    for field in REQUIRED_LIST_FIELDS:
        if not isinstance(payload.get(field), list):
            errors.append(f"{field} must be a list")
    for field in REQUIRED_OBJECT_FIELDS:
        if not isinstance(payload.get(field), dict):
            errors.append(f"{field} must be an object")
    for field in REQUIRED_FALSE_FIELDS:
        if payload.get(field) is not False:
            errors.append(f"{field} must be false")
    return errors


def validate_adoption_surface_artifact(path: str | Path) -> list[str]:
    artifact = Path(path)
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"artifact could not be read: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"artifact is not valid JSON: {exc}"]
    return validate_adoption_surface_payload(payload)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption-surface",
        description="Write a read-only adoption surface discovery artifact.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="build/sdetkit/adoption-surface.json")
    parser.add_argument("--format", choices=["json", "text", "report"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)
    summary = write_adoption_surface_artifact(repo_root=ns.root, out=ns.out)
    if ns.format == "json":
        sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    elif ns.format == "report":
        payload = json.loads(Path(summary["adoption_surface_json"]).read_text(encoding="utf-8"))
        sys.stdout.write(render_adoption_surface_report(payload) + "\n")
    else:
        sys.stdout.write(f"adoption_surface_json={summary['adoption_surface_json']}\n")
        sys.stdout.write(f"automation_allowed={str(summary['automation_allowed']).lower()}\n")
        sys.stdout.write(
            f"patch_application_allowed={str(summary['patch_application_allowed']).lower()}\n"
        )
        sys.stdout.write(f"merge_authorized={str(summary['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(summary['semantic_equivalence_proven']).lower()}\n"
        )
    return 0
