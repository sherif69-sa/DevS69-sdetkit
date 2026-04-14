from __future__ import annotations

from importlib import metadata

from sdetkit import versioning


def test_tool_version_uses_installed_package_version(monkeypatch) -> None:
    monkeypatch.setattr(versioning.metadata, "version", lambda _name: "9.9.9")
    assert versioning.tool_version() == "9.9.9"


def test_tool_version_handles_missing_package(monkeypatch) -> None:
    def _raise(_name: str) -> str:
        raise metadata.PackageNotFoundError

    monkeypatch.setattr(versioning.metadata, "version", _raise)
    assert versioning.tool_version() == "0+unknown"
