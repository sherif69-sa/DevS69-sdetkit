from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_FILE = ROOT / "tools" / "enforce_branch_protection.py"
ENFORCE_WORKFLOW = ROOT / ".github" / "workflows" / "enforce-branch-protection.yml"
LEGACY_BRIDGE_WORKFLOW = ROOT / ".github" / "workflows" / "legacy-required-status-bridge.yml"

_SPEC = importlib.util.spec_from_file_location("enforce_branch_protection", TOOLS_FILE)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def test_default_required_checks_match_workflow_contracts() -> None:
    bridge_text = LEGACY_BRIDGE_WORKFLOW.read_text(encoding="utf-8")
    assert "contexts = ['ci', 'maintenance-autopilot']" in bridge_text

    assert tuple(_MOD.DEFAULT_REQUIRED_CHECKS) == (
        "ci",
        "maintenance-autopilot",
    )


def test_enforcement_workflow_uses_default_required_checks() -> None:
    text = ENFORCE_WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in text
    assert "pull_request_target:" not in text
    assert "--enforce-admins" in text
    assert "--disable-pr-reviews" in text
    for context in _MOD.DEFAULT_REQUIRED_CHECKS:
        assert f'--required-check "{context}"' in text
