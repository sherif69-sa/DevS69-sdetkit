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
        "operations-readiness-signal": ["baseline-readiness-signal"],
        "operations-remediation-plan": ["baseline-followup-pass"],
        "operations-run": ["baseline-run"],
        "operations-quality-gate": ["baseline-release-readiness-gate"],
        "operations-cleanup-plan": ["baseline-transition-plan"],
        "operations-finalize": ["baseline-completion-report"],
    }

    for alias, target in expected.items():
        assert _target_dependencies(alias) == target


def test_baseline_targets_are_first_class_professional_targets() -> None:
    expected = {
        "baseline-readiness-signal": ["venv"],
        "baseline-followup-pass": ["venv"],
        "baseline-run": [
            "baseline-run-all",
            "baseline-artifact-set",
            "baseline-telemetry",
            "baseline-readiness-signal",
        ],
        "baseline-transition-plan": ["venv"],
        "baseline-release-readiness-gate": ["venv"],
        "baseline-completion-report": ["venv"],
    }

    banned_fragments = ("phase", "do-it", "closeout", "finish-signal", "next-pass", "retire-plan")

    for target, deps in expected.items():
        assert _target_dependencies(target) == deps
        for fragment in banned_fragments:
            assert fragment not in target
            assert all(fragment not in dep for dep in deps)
