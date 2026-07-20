from __future__ import annotations

from importlib import metadata
from pathlib import Path

import tomllib

from sdetkit import repo


def test_repo_audit_version_falls_back_to_source_project_metadata(monkeypatch) -> None:
    def missing_distribution(_name: str) -> str:
        raise metadata.PackageNotFoundError

    monkeypatch.setattr(repo.importlib_metadata, "version", missing_distribution)
    payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    expected = payload["project"]["version"]

    assert repo._tool_version() == expected
    assert repo._tool_version() != "1.0.0"
