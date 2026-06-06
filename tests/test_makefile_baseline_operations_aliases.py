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
    targets = (
        "baseline-readiness-signal",
        "baseline-followup-pass",
        "baseline-run",
        "baseline-transition-plan",
        "baseline-release-readiness-gate",
        "baseline-completion-report",
    )

    banned_fragments = ("phase", "do-it", "closeout", "finish-signal", "next-pass", "retire-plan")

    for target in targets:
        deps = _target_dependencies(target)
        assert deps, f"{target} should have an implementation dependency"
        for fragment in banned_fragments:
            assert fragment not in target
