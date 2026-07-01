from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "osv-scanner.yml"
FIXTURE = ROOT / "tests" / "fixtures" / "public_adoption_target"


def test_osv_repo_scan_preserves_root_coverage_and_excludes_non_runtime_fixture() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    normalized_lines = {line.strip() for line in workflow.splitlines()}

    assert "-r" in normalized_lines
    assert "./" in normalized_lines
    assert "--exclude=tests/fixtures/public_adoption_target" in normalized_lines
    assert "upload-sarif: true" in normalized_lines


def test_public_adoption_fixture_uses_current_security_toolchain_markers() -> None:
    requirement = (FIXTURE / "requirements-security.txt").read_text(encoding="utf-8").strip()
    requirement_match = re.fullmatch(r"pip-audit==(\d+)\.(\d+)\.(\d+)", requirement)
    assert requirement_match is not None
    assert tuple(int(part) for part in requirement_match.groups()) >= (2, 10, 1)

    go_mod = (FIXTURE / "go.mod").read_text(encoding="utf-8")
    go_match = re.search(r"^go (\d+)\.(\d+)$", go_mod, flags=re.MULTILINE)
    assert go_match is not None
    assert tuple(int(part) for part in go_match.groups()) >= (1, 26)
