from __future__ import annotations

from pathlib import Path

MAKEFILE = Path("Makefile")


def _target_dependencies(target: str) -> list[str]:
    prefix = f"{target}:"
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).split()
    raise AssertionError(f"missing Makefile target: {target}")


def test_current_status_targets_are_first_class_professional_targets() -> None:
    assert _target_dependencies("operations-current-status") == ["venv"]
    assert _target_dependencies("operations-current-status-json") == ["venv"]


def test_operations_current_aliases_route_through_professional_targets() -> None:
    assert _target_dependencies("operations-current") == ["operations-current-status"]
    assert _target_dependencies("operations-current-json") == ["operations-current-status-json"]


def test_legacy_phase_current_targets_remain_compatible() -> None:
    assert _target_dependencies("phase-current") == ["operations-current-status"]
    assert _target_dependencies("phase-current-json") == ["operations-current-status-json"]


def test_plan_status_uses_professional_status_payload() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert _target_dependencies("plan-status") == ["operations-current-status-json"]
    assert "use operations-current-status-json output as canonical status payload" in makefile
