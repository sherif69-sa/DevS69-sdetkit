from __future__ import annotations

from pathlib import Path

MAKEFILE = Path("Makefile")


def _target_dependencies(target: str) -> list[str]:
    prefix = f"{target}:"
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).split()
    raise AssertionError(f"missing Makefile target: {target}")


def test_phase1_entrypoints_remain_compatibility_aliases() -> None:
    expected = {
        "phase1-baseline": ["baseline-foundation"],
        "phase1-next": ["baseline-next-action"],
        "phase1-dashboard": ["baseline-dashboard"],
        "phase1-control-loop": ["baseline-control-loop"],
    }

    for legacy_target, professional_target in expected.items():
        assert _target_dependencies(legacy_target) == professional_target
