from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _single_match(pattern: str, content: str, source: str) -> str:
    matches = re.findall(pattern, content, flags=re.MULTILINE)
    assert len(matches) == 1, f"expected one Ruff pin in {source}, found {len(matches)}"
    return matches[0]


def test_ruff_version_is_aligned_across_toolchain_surfaces() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    constraints = (ROOT / "constraints-ci.txt").read_text(encoding="utf-8")
    pre_commit = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))

    pyproject_version = _single_match(r'^\s*"ruff==([^"\s]+)"', pyproject, "pyproject.toml")
    constraints_version = _single_match(r"^ruff==([^\s#]+)", constraints, "constraints-ci.txt")
    ruff_repositories = [
        repository
        for repository in pre_commit["repos"]
        if repository["repo"] == "https://github.com/astral-sh/ruff-pre-commit"
    ]

    assert len(ruff_repositories) == 1
    pre_commit_version = str(ruff_repositories[0]["rev"]).removeprefix("v")
    assert pre_commit_version == pyproject_version == constraints_version
