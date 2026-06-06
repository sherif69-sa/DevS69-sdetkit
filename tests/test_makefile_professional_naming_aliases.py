from __future__ import annotations

import re
from pathlib import Path

MAKEFILE = Path("Makefile")


def _target_dependencies(target: str) -> list[str]:
    text = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(target)}:([^\n]*)$", text, re.MULTILINE)
    assert match is not None, f"missing Makefile target: {target}"
    return match.group(1).split()


def test_platform_readiness_quality_aliases_are_primary_makefile_surface() -> None:
    assert _target_dependencies("platform-readiness-dependency-radar") == [
        "phase3-dependency-radar"
    ]
    assert _target_dependencies("platform-readiness-quality-report") == ["phase3-quality-report"]
    assert _target_dependencies("platform-readiness-quality-run") == [
        "platform-readiness-quality-report"
    ]


def test_neutral_quality_contract_aliases_use_professional_targets() -> None:
    assert _target_dependencies("quality-contract-report") == ["platform-readiness-quality-report"]
    assert _target_dependencies("quality-contract-run") == ["platform-readiness-quality-run"]


def test_legacy_phase3_do_it_remains_compatibility_only() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "phase3-do-it: platform-readiness-quality-contract" in text
    assert "phase3-do-it is deprecated; use phase3-quality-report" in text
    assert text.index("platform-readiness-quality-run:") < text.index("phase3-do-it:")
