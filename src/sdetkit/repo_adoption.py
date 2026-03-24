from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RepoDetection:
    root: str
    is_git_repo: bool
    has_pyproject: bool
    has_tests: bool
    has_src_layout: bool
    has_pytest: bool
    has_nox: bool
    has_tox: bool
    has_docs: bool
    has_github_workflows: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProfileRecommendation:
    profile: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_git_repo(root: Path) -> bool:
    if (root / ".git").exists():
        return True
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def detect_repo(root: Path) -> RepoDetection:
    pyproject = root / "pyproject.toml"
    pytest_ini = root / "pytest.ini"
    requirements_test = root / "requirements-test.txt"
    noxfile = root / "noxfile.py"
    tox_ini = root / "tox.ini"
    docs_dir = root / "docs"
    mkdocs_yml = root / "mkdocs.yml"
    workflows = root / ".github" / "workflows"

    pyproject_text = _read_text(pyproject)

    has_tests = (root / "tests").is_dir()
    has_src_layout = (root / "src").is_dir()
    has_pyproject = pyproject.is_file()
    has_nox = noxfile.is_file()
    has_tox = tox_ini.is_file()
    has_docs = docs_dir.is_dir() or mkdocs_yml.is_file()
    has_github_workflows = workflows.is_dir()
    has_pytest = (
        pytest_ini.is_file()
        or requirements_test.is_file()
        or has_tests
        or "pytest" in pyproject_text
    )

    return RepoDetection(
        root=str(root.resolve()),
        is_git_repo=_is_git_repo(root),
        has_pyproject=has_pyproject,
        has_tests=has_tests,
        has_src_layout=has_src_layout,
        has_pytest=has_pytest,
        has_nox=has_nox,
        has_tox=has_tox,
        has_docs=has_docs,
        has_github_workflows=has_github_workflows,
    )


def recommend_profile(detected: RepoDetection) -> ProfileRecommendation:
    mature_signals = sum(
        [
            detected.has_pyproject,
            detected.has_tests,
            detected.has_src_layout,
            detected.has_pytest,
            detected.has_nox or detected.has_tox,
            detected.has_docs,
            detected.has_github_workflows,
        ]
    )
    if mature_signals >= 6:
        return ProfileRecommendation(
            profile="strict",
            reason="repo has strong packaging, test, CI, and documentation signals",
        )
    if mature_signals >= 3:
        return ProfileRecommendation(
            profile="standard",
            reason="repo has enough source and test structure for normal validation",
        )
    return ProfileRecommendation(
        profile="quick",
        reason="repo appears minimal, so quick adoption is the safest starting point",
    )


def build_init_payload(root: Path, *, preset: str) -> dict[str, Any]:
    detected = detect_repo(root)
    recommendation = recommend_profile(detected)
    return {
        "schema_version": "sdetkit.repo-init.v1",
        "root": str(root.resolve()),
        "preset": preset,
        "detected": detected.to_dict(),
        "recommended_profile": recommendation.profile,
        "recommendation_reason": recommendation.reason,
        "next_commands": [
            f"python -m sdetkit check --profile {recommendation.profile}",
            "bash quality.sh ci",
            "bash quality.sh verify",
        ],
    }


def render_init_payload(payload: dict[str, Any], *, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, indent=2, sort_keys=True)

    detected = payload["detected"]
    lines = [
        "repo init adoption summary",
        f"root: {payload['root']}",
        f"preset: {payload['preset']}",
        "detected:",
    ]
    for key, value in detected.items():
        if key == "root":
            continue
        if value:
            lines.append(f"- {key}")
    lines.append(f"recommended profile: {payload['recommended_profile']}")
    lines.append(f"reason: {payload['recommendation_reason']}")
    lines.append("next:")
    for cmd in payload["next_commands"]:
        lines.append(f"- {cmd}")
    return "\n".join(lines)
