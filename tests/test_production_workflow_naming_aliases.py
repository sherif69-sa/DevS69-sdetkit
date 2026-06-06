from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"

ALIASES = {
    "quality-contract-check": "platform-readiness-quality-contract",
    "quality-contract-report": "platform-readiness-quality-report",
    "quality-contract-run": "platform-readiness-quality-run",
    "operations-baseline": "phase1-baseline",
    "operations-status": "phase1-status",
    "operations-next-action": "phase1-next",
    "operations-snapshot": "phase1-ops-snapshot",
    "operations-dashboard": "phase1-dashboard",
    "operations-weekly-pack": "phase1-weekly-pack",
    "operations-control-loop": "phase1-control-loop",
    "operations-run-all": "phase1-run-all",
    "operations-artifact-set": "phase1-artifact-set",
    "operations-telemetry": "phase1-telemetry",
    "operations-readiness-signal": "phase1-finish-signal",
    "operations-remediation-plan": "phase1-next-pass",
    "operations-blocker-register": "phase1-blocker-register",
    "operations-run": "phase1-do-it",
    "operations-core-run": "phase1-execution-core",
    "operations-workflow": "phase1-workflow",
    "operations-flow-contract": "phase1-flow-contract",
    "operations-quality-gate": "phase1-gate-phase2",
    "operations-executive-report": "phase1-executive-report",
    "operations-cleanup-plan": "phase1-retire-plan",
    "operations-complete": "phase1-complete",
    "operations-finalize": "phase1-closeout",
    "operations-current": "phase-current",
    "operations-current-json": "phase-current-json",
    "governance-contract-check": "operational-readiness-governance-contract",
    "ecosystem-contract-check": "phase5-ecosystem-contract",
    "metrics-contract-check": "phase6-metrics-contract",
}


def test_production_workflow_aliases_point_to_supported_targets() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    for alias, target in ALIASES.items():
        assert f"{alias}: {target}" in makefile


def test_new_alias_names_avoid_internal_sequence_language() -> None:
    banned_fragments = (
        "phase",
        "do-it",
        "closeout",
        "finish-signal",
        "retire-plan",
        "next-pass",
        "gate-phase",
    )

    for alias in ALIASES:
        for fragment in banned_fragments:
            assert fragment not in alias
