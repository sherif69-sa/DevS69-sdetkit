from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_FILE = ROOT / "tools" / "enforce_branch_protection.py"
ENFORCE_WORKFLOW = ROOT / ".github" / "workflows" / "enforce-branch-protection.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
AUTOPILOT_WORKFLOW = ROOT / ".github" / "workflows" / "maintenance-autopilot.yml"

_SPEC = importlib.util.spec_from_file_location("enforce_branch_protection", TOOLS_FILE)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def test_default_required_checks_match_workflow_contracts() -> None:
    ci_text = CI_WORKFLOW.read_text(encoding="utf-8")
    autopilot_text = AUTOPILOT_WORKFLOW.read_text(encoding="utf-8")

    assert "name: CI" in ci_text
    assert "full-ci:" in ci_text
    assert "name: Full CI lane" in ci_text

    assert "name: maintenance-autopilot" in autopilot_text
    assert "autopilot:" in autopilot_text

    assert tuple(_MOD.DEFAULT_REQUIRED_CHECKS) == (
        "CI / Full CI lane",
        "maintenance-autopilot / autopilot",
    )


def test_enforcement_workflow_uses_default_required_checks() -> None:
    text = ENFORCE_WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target:" in text
    for context in _MOD.DEFAULT_REQUIRED_CHECKS:
        assert f'--required-check "{context}"' in text
