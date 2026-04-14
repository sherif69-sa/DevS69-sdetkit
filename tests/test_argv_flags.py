from __future__ import annotations

from sdetkit.argv_flags import extract_global_flag


def test_extract_global_flag_when_present() -> None:
    argv, found = extract_global_flag(["--no-legacy-hint", "gate", "fast"], "--no-legacy-hint")
    assert found is True
    assert argv == ["gate", "fast"]


def test_extract_global_flag_when_missing() -> None:
    argv, found = extract_global_flag(["gate", "fast"], "--no-legacy-hint")
    assert found is False
    assert argv == ["gate", "fast"]
