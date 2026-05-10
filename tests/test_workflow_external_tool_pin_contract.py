from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(".")
WORKFLOW_DIR = ROOT / ".github" / "workflows"

PINNED_TOOLS = {
    "pip-audit": {
        "requirement_files": [ROOT / "requirements.txt"],
        "workflow_files": [WORKFLOW_DIR / "dependency-audit.yml"],
    },
    "cyclonedx-bom": {
        "requirement_files": [ROOT / "requirements.txt"],
        "workflow_files": [WORKFLOW_DIR / "sbom.yml"],
    },
}


def _requirement_pin(tool: str, files: list[Path]) -> str:
    pattern = re.compile(rf"^{re.escape(tool)}==([^\s#]+)")
    matches: list[str] = []

    for path in files:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            match = pattern.match(line.strip())
            if match:
                matches.append(match.group(1))

    assert matches, f"No requirement pin found for {tool}"
    assert len(set(matches)) == 1, f"Conflicting requirement pins for {tool}: {matches}"
    return matches[0]


def _workflow_pins(tool: str, files: list[Path]) -> list[str]:
    pattern = re.compile(rf"{re.escape(tool)}==([^\s\"'`]+)")
    pins: list[str] = []

    for path in files:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            match = pattern.search(line)
            if match:
                pins.append(match.group(1))

    return pins


def test_external_tool_workflow_pins_match_requirement_truth() -> None:
    offenders: list[str] = []

    for tool, config in PINNED_TOOLS.items():
        expected = _requirement_pin(tool, config["requirement_files"])
        actual_pins = _workflow_pins(tool, config["workflow_files"])
        for actual in actual_pins:
            if actual != expected:
                offenders.append(f"{tool}: workflow={actual} requirements={expected}")

    assert not offenders, (
        "Workflow external tool pins must match the repo requirement truth "
        "when the tool is already pinned in requirements files:\n" + "\n".join(offenders)
    )
