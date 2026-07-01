from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "public_adoption_target"


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def test_public_adoption_fixture_requires_current_python_audit_tool() -> None:
    requirement = (FIXTURE / "requirements-security.txt").read_text(encoding="utf-8").strip()
    match = re.fullmatch(r"pip-audit>=(\d+\.\d+\.\d+)", requirement)

    assert match is not None
    assert _version_tuple(match.group(1)) >= (2, 10, 1)


def test_public_adoption_fixture_requires_current_go_toolchain() -> None:
    go_mod = (FIXTURE / "go.mod").read_text(encoding="utf-8")
    language = re.search(r"^go (\d+\.\d+)$", go_mod, flags=re.MULTILINE)
    toolchain = re.search(r"^toolchain go(\d+\.\d+\.\d+)$", go_mod, flags=re.MULTILINE)

    assert language is not None
    assert _version_tuple(language.group(1)) >= (1, 26)
    assert toolchain is not None
    assert _version_tuple(toolchain.group(1)) >= (1, 26, 4)


def test_public_adoption_fixture_declares_local_scanner_policy() -> None:
    policy_path = FIXTURE / "osv-scanner.toml"
    policy = policy_path.read_text(encoding="utf-8")

    assert policy_path.is_file()
    assert "[[PackageOverrides]]" in policy
    assert "Fixture-only public adoption target" in policy
    assert "not a production or release dependency" in policy
