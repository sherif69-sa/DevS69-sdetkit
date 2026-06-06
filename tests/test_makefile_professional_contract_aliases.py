from __future__ import annotations

from pathlib import Path

MAKEFILE = Path("Makefile")


def _target_dependencies(target: str) -> list[str]:
    prefix = f"{target}:"
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).split()
    raise AssertionError(f"missing Makefile target: {target}")


def test_quality_contract_public_aliases_route_to_supported_targets() -> None:
    assert _target_dependencies("quality-contract-check") == ["platform-readiness-quality-contract"]
    assert _target_dependencies("quality-contract-report") == ["platform-readiness-quality-report"]
    assert _target_dependencies("quality-contract-run") == ["platform-readiness-quality-run"]


def test_platform_readiness_targets_preserve_phase3_compatibility() -> None:
    assert _target_dependencies("platform-readiness-dependency-radar") == [
        "phase3-dependency-radar"
    ]
    assert _target_dependencies("platform-readiness-quality-report") == ["phase3-quality-report"]
    assert _target_dependencies("platform-readiness-quality-run") == [
        "platform-readiness-quality-report"
    ]
    assert _target_dependencies("phase3-do-it") == ["platform-readiness-quality-contract"]


def test_governance_ecosystem_and_metrics_public_aliases_remain_stable() -> None:
    assert _target_dependencies("governance-contract-check") == [
        "operational-readiness-governance-contract"
    ]
    assert _target_dependencies("ecosystem-contract-check") == ["phase5-ecosystem-contract"]
    assert _target_dependencies("metrics-contract-check") == ["phase6-metrics-contract"]
