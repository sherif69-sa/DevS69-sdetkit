from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"

LEGACY_MAKE_COMMAND = re.compile(r"\bmake\s+phase\d[\w-]*\b")

EXPECTED_WORKFLOW_ALIASES = {
    "phase3-quality-contract.yml": "make quality-contract-run",
    "phase4-governance-contract.yml": "make governance-contract-check",
    "phase5-ecosystem-contract.yml": "make ecosystem-contract-check",
    "phase6-metrics-contract.yml": "make metrics-contract-check",
}

CONTRACT_SCRIPT_EXPECTATIONS = {
    "scripts/check_phase1_flow_contract.py": {
        "required": {
            "docs/operations-execution-guide.md",
        },
        "forbidden": {
            "docs/phase-execution-one-by-one.md",
            "docs/phase-by-phase-execution-plan.md",
            "docs/phase1-execution-checklist.md",
            "operations-next-action-pass",
        },
    },
    "scripts/check_phase4_governance_contract.py": {
        "required": {
            '"make governance-contract-check"',
            '"make quality-contract-check"',
        },
        "forbidden": {
            '"make phase4-governance-contract"',
            '"make phase3-quality-contract"',
        },
    },
}


def test_workflow_yaml_uses_production_make_aliases() -> None:
    violations: list[str] = []

    for path in sorted(WORKFLOW_ROOT.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = LEGACY_MAKE_COMMAND.search(line)
            if match:
                rel = path.relative_to(ROOT).as_posix()
                violations.append(f"{rel}:{line_number}: replace {match.group()!r}")

    assert not violations, "\n".join(violations)


def test_known_workflows_keep_expected_production_aliases() -> None:
    for workflow_name, command in EXPECTED_WORKFLOW_ALIASES.items():
        path = WORKFLOW_ROOT / workflow_name
        if not path.exists():
            continue

        text = path.read_text(encoding="utf-8")
        assert command in text


def test_contract_scripts_track_production_workflow_names() -> None:
    for file_name, expectations in CONTRACT_SCRIPT_EXPECTATIONS.items():
        text = (ROOT / file_name).read_text(encoding="utf-8")

        for required in sorted(expectations["required"]):
            assert required in text

        for forbidden in sorted(expectations["forbidden"]):
            assert forbidden not in text
