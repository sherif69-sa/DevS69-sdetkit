"""One repository model shared by gate, doctor, init and fit.

The adoption surface already discovers what a repository is made of across
Python, JavaScript/TypeScript, Go, Java, Rust, .NET and C++, and which CI
systems run it. This module reads that discovery once and answers the
questions the decision commands ask, so they stop re-detecting the repository
with their own Python-only checks.

Discovery is read-only. The model names the repository's own test commands;
it never decides on its own to run them.
"""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .adoption_surface import discover_adoption_surface
from .adoption_surface.core import shared_walk, walk_files

SCHEMA_VERSION = "sdetkit.repo_model.v1"

CI_SURFACES = frozenset({"azure_devops", "circleci", "github_actions", "gitlab_ci", "jenkins"})
# A workspace's proof runs in this order; a later stage needs the earlier ones.
SUITE_STAGES = ("configure", "build", "test")
_TRUSTED_CONFIDENCE = frozenset({"high", "medium"})
# Lint and format tools whose presence in a CI file means CI enforces code quality.
CI_QUALITY_TOOLS = (
    "cargo clippy",
    "cargo fmt",
    "checkstyle",
    "clang-format",
    "clang-tidy",
    "dotnet format",
    "eslint",
    "flake8",
    "gofmt",
    "golangci-lint",
    "mypy",
    "pre-commit",
    "prettier",
    "pylint",
    "ruff",
    "spotless",
)
# Security scanners whose presence in a CI file means CI scans the code or dependencies.
CI_SECURITY_TOOLS = (
    "bandit",
    "cargo audit",
    "codeql",
    "dependency-check",
    "gitleaks",
    "gosec",
    "govulncheck",
    "grype",
    "npm audit",
    "osv-scanner",
    "pip-audit",
    "pnpm audit",
    "semgrep",
    "snyk",
    "trivy",
    "trufflehog",
    "yarn audit",
)
_PYTHON_TEST_DIRS = ("tests", "test")


@dataclass(frozen=True)
class TestSuite:
    """One workspace's own test command chain (configure, build, test)."""

    ecosystem: str
    working_directory: str
    commands: tuple[str, ...]
    evidence: tuple[str, ...] = ()

    @property
    def step_id(self) -> str:
        if self.working_directory == ".":
            return f"tests:{self.ecosystem}"
        return f"tests:{self.ecosystem}:{self.working_directory}"

    def argv(self) -> list[list[str]]:
        return [shlex.split(command) for command in self.commands]

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "ecosystem": self.ecosystem,
            "working_directory": self.working_directory,
            "commands": list(self.commands),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class RepoModel:
    root: Path
    languages: tuple[str, ...]
    ci_systems: tuple[str, ...]
    ci_files: tuple[str, ...]
    package_managers: tuple[str, ...]
    security_tools: tuple[str, ...]
    ci_security_evidence: tuple[str, ...]
    quality_commands: tuple[str, ...]
    test_suites: tuple[TestSuite, ...]
    file_count: int
    python_sources: bool
    surface: Mapping[str, Any] = field(repr=False, compare=False, default_factory=dict)

    @property
    def has_python(self) -> bool:
        return "python" in self.languages or self.python_sources

    @property
    def other_languages(self) -> tuple[str, ...]:
        return tuple(language for language in self.languages if language != "python")

    def _ci_mentions(self, tools: tuple[str, ...]) -> set[str]:
        found: set[str] = set()
        for rel in self.ci_files:
            try:
                text = (self.root / rel).read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            found.update(tool for tool in tools if tool in text)
        return found

    def ci_quality_tools(self) -> tuple[str, ...]:
        """Lint and format tools a CI file invokes."""

        return tuple(sorted(self._ci_mentions(CI_QUALITY_TOOLS)))

    def ci_security_tools(self) -> tuple[str, ...]:
        """Security scanners a CI file invokes, by discovery evidence or by name."""

        return tuple(sorted(set(self.ci_security_evidence) | self._ci_mentions(CI_SECURITY_TOOLS)))

    def non_python_suites(self) -> tuple[TestSuite, ...]:
        return tuple(suite for suite in self.test_suites if suite.ecosystem != "python")

    def size(self) -> str:
        if self.file_count >= 2000:
            return "large"
        if self.file_count >= 200:
            return "medium"
        return "small"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "languages": list(self.languages),
            "ci_systems": list(self.ci_systems),
            "ci_files": list(self.ci_files),
            "package_managers": list(self.package_managers),
            "security_tools": list(self.security_tools),
            "ci_quality_tools": list(self.ci_quality_tools()),
            "ci_security_tools": list(self.ci_security_tools()),
            "quality_commands": list(self.quality_commands),
            "test_suites": [suite.to_dict() for suite in self.test_suites],
            "file_count": self.file_count,
            "size": self.size(),
            "has_python": self.has_python,
        }


def _names(items: Any) -> tuple[str, ...]:
    if not isinstance(items, list):
        return ()
    return tuple(
        sorted({str(item["name"]) for item in items if isinstance(item, dict) and item.get("name")})
    )


def _files_of(items: Any) -> tuple[str, ...]:
    if not isinstance(items, list):
        return ()
    return tuple(
        sorted(
            {
                str(path)
                for item in items
                if isinstance(item, dict)
                for path in (item.get("files") or item.get("evidence") or [])
            }
        )
    )


def _ci_security_tools(items: Any, ci_files: tuple[str, ...]) -> tuple[str, ...]:
    """Security tools with evidence in a CI file, so CI is what runs them."""

    if not isinstance(items, list):
        return ()
    ci = set(ci_files)
    return tuple(
        sorted(
            {
                str(item["name"])
                for item in items
                if isinstance(item, dict)
                and item.get("name")
                and ci.intersection(
                    str(path) for path in (item.get("evidence") or item.get("files") or [])
                )
            }
        )
    )


def _test_suites(commands: list[Any], languages: tuple[str, ...]) -> tuple[TestSuite, ...]:
    grouped: dict[tuple[str, str], dict[str, list[str]]] = {}
    evidence: dict[tuple[str, str], set[str]] = {}
    for item in commands:
        if not isinstance(item, dict):
            continue
        surface = str(item.get("surface") or "")
        stage = str(item.get("purpose") or "")
        command = str(item.get("command") or "").strip()
        if (
            not command
            or surface in CI_SURFACES
            or surface not in languages
            or stage not in SUITE_STAGES
            or item.get("confidence") not in _TRUSTED_CONFIDENCE
        ):
            continue
        raw_source = item.get("source")
        source: dict[str, Any] = raw_source if isinstance(raw_source, dict) else {}
        working_directory = PurePosixPath(str(source.get("working_directory") or ".")).as_posix()
        if working_directory.startswith("/") or ".." in PurePosixPath(working_directory).parts:
            continue  # a suite runs inside the repository or not at all
        key = (surface, working_directory)
        stages = grouped.setdefault(key, {})
        if command not in stages.setdefault(stage, []):
            stages[stage].append(command)
        evidence.setdefault(key, set()).update(str(path) for path in item.get("evidence") or [])
    suites = []
    for (surface, working_directory), stages in sorted(grouped.items()):
        if "test" not in stages:
            continue
        chain = tuple(command for stage in SUITE_STAGES for command in stages.get(stage, []))
        suites.append(
            TestSuite(
                ecosystem=surface,
                working_directory=working_directory,
                commands=chain,
                evidence=tuple(sorted(evidence.get((surface, working_directory), ()))),
            )
        )
    return tuple(suites)


def _python_sources(files: tuple[str, ...]) -> bool:
    for path in files:
        if not path.endswith(".py"):
            continue
        if "/" not in path or path.split("/", 1)[0] in _PYTHON_TEST_DIRS:
            return True
    return False


def build_repo_model(root: str | Path = ".") -> RepoModel:
    """Discover the repository once and return the shared model."""

    repo_root = Path(root)
    with shared_walk():
        surface = discover_adoption_surface(repo_root)
        files = walk_files(repo_root)
    languages = _names(surface.get("detected_languages"))
    commands = surface.get("recommended_proof_commands")
    command_items = commands if isinstance(commands, list) else []
    quality = tuple(
        sorted(
            {
                str(item.get("command"))
                for item in command_items
                if isinstance(item, dict) and item.get("purpose") in {"quality", "lint"}
            }
        )
    )
    ci_files = _files_of(surface.get("ci_systems"))
    return RepoModel(
        root=repo_root,
        languages=languages,
        ci_systems=_names(surface.get("ci_systems")),
        ci_files=ci_files,
        package_managers=_names(surface.get("package_managers")),
        security_tools=_names(surface.get("security_tools")),
        ci_security_evidence=_ci_security_tools(surface.get("security_tools"), ci_files),
        quality_commands=quality,
        test_suites=_test_suites(command_items, languages),
        file_count=len(files),
        python_sources=_python_sources(files),
        surface=surface,
    )
