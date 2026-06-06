from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"

ALIASES = {
    "quality-contract-check": "platform-readiness-quality-contract",
    "quality-contract-report": "platform-readiness-quality-report",
    "quality-contract-run": "platform-readiness-quality-run",
    "operations-baseline": "phase1-baseline",
    "operations-status": "baseline-status",
    "operations-next-action": "phase1-next",
    "operations-snapshot": "baseline-ops-snapshot",
    "operations-dashboard": "phase1-dashboard",
    "operations-weekly-pack": "baseline-weekly-pack",
    "operations-control-loop": "phase1-control-loop",
    "operations-run-all": "baseline-run-all",
    "operations-artifact-set": "baseline-artifact-set",
    "operations-telemetry": "baseline-telemetry",
    "operations-readiness-signal": "baseline-readiness-signal",
    "operations-remediation-plan": "baseline-followup-pass",
    "operations-blocker-register": "baseline-blocker-register",
    "operations-run": "baseline-run",
    "operations-core-run": "baseline-execution-core",
    "operations-workflow": "baseline-workflow",
    "operations-flow-contract": "baseline-flow-contract",
    "operations-quality-gate": "baseline-release-readiness-gate",
    "operations-executive-report": "baseline-executive-report",
    "operations-cleanup-plan": "baseline-transition-plan",
    "operations-complete": "baseline-complete",
    "operations-finalize": "baseline-completion-report",
    "operations-current": "operations-current-status",
    "operations-current-json": "operations-current-status-json",
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
