from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
ALIASES = ROOT / "docs" / "naming" / "professional-command-aliases.json"


def test_professional_readiness_command_aliases_delegate_to_legacy_targets() -> None:
    makefile_lines = set(MAKEFILE.read_text(encoding="utf-8").splitlines())
    payload = json.loads(ALIASES.read_text(encoding="utf-8"))

    for item in payload["aliases_added"]:
        professional = item["professional"]
        legacy = item["legacy"]

        assert f".PHONY: {professional}" in makefile_lines
        assert f"{professional}: {legacy}" in makefile_lines
