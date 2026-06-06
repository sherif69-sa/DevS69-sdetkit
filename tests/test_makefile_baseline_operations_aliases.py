from __future__ import annotations

from pathlib import Path

MAKEFILE = Path("Makefile")


def _target_dependencies(target: str) -> list[str]:
    prefix = f"{target}:"
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).split()
    raise AssertionError(f"missing Makefile target: {target}")


def test_operations_aliases_route_through_baseline_names() -> None:
    expected = {
        "operations-status": ["baseline-status"],
        "operations-snapshot": ["baseline-ops-snapshot"],
        "operations-weekly-pack": ["baseline-weekly-pack"],
        "operations-run-all": ["baseline-run-all"],
        "operations-artifact-set": ["baseline-artifact-set"],
        "operations-telemetry": ["baseline-telemetry"],
        "operations-readiness-signal": ["baseline-readiness-signal"],
        "operations-remediation-plan": ["baseline-followup-pass"],
        "operations-blocker-register": ["baseline-blocker-register"],
        "operations-run": ["baseline-run"],
        "operations-core-run": ["baseline-execution-core"],
        "operations-workflow": ["baseline-workflow"],
        "operations-flow-contract": ["baseline-flow-contract"],
        "operations-quality-gate": ["baseline-release-readiness-gate"],
        "operations-executive-report": ["baseline-executive-report"],
        "operations-cleanup-plan": ["baseline-transition-plan"],
        "operations-complete": ["baseline-complete"],
        "operations-finalize": ["baseline-completion-report"],
    }

    for alias, target in expected.items():
        assert _target_dependencies(alias) == target


def test_baseline_targets_are_first_class_professional_targets() -> None:
    expected = {
        "baseline-status": ["venv"],
        "baseline-ops-snapshot": ["venv"],
        "baseline-weekly-pack": ["venv"],
        "baseline-run-all": ["venv"],
        "baseline-artifact-set": ["venv"],
        "baseline-telemetry": ["venv"],
        "baseline-readiness-signal": ["venv"],
        "baseline-followup-pass": ["venv"],
        "baseline-blocker-register": ["venv"],
        "baseline-execution-core": [
            "baseline-run-all",
            "baseline-artifact-set",
            "baseline-telemetry",
            "baseline-readiness-signal",
        ],
        "baseline-run": [
            "baseline-run-all",
            "baseline-artifact-set",
            "baseline-telemetry",
            "baseline-readiness-signal",
        ],
        "baseline-workflow": [
            "baseline-execution-core",
            "baseline-flow-contract",
            "baseline-release-readiness-gate",
            "baseline-executive-report",
        ],
        "baseline-flow-contract": ["venv"],
        "baseline-release-readiness-gate": ["venv"],
        "baseline-executive-report": ["venv"],
        "baseline-transition-plan": ["venv"],
        "baseline-completion-report": ["venv"],
        "baseline-complete": ["install"],
    }

    banned_fragments = ("phase", "do-it", "closeout", "finish-signal", "next-pass", "retire-plan")

    for target, deps in expected.items():
        assert _target_dependencies(target) == deps
        for fragment in banned_fragments:
            assert fragment not in target
            assert all(fragment not in dep for dep in deps)
