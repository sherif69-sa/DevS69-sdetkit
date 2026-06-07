from __future__ import annotations

from pathlib import Path

SURFACE_DOC = Path("docs/naming/professional-public-command-surface.md")
OPERATOR_DOC = Path("docs/operator-essentials.md")


def test_professional_public_command_surface_doc_exists() -> None:
    text = SURFACE_DOC.read_text(encoding="utf-8")

    required = [
        "make operations-baseline",
        "make release-readiness-start",
        "make quality-contract-report",
        "make ecosystem-contract-check",
        "make metrics-contract-check",
    ]

    for command in required:
        assert command in text


def test_operator_essentials_prefers_professional_rollout_commands() -> None:
    text = OPERATOR_DOC.read_text(encoding="utf-8")

    required = [
        "make operations-baseline",
        "make release-readiness-start",
        "make release-readiness-workflow",
        "make release-readiness-status",
        "make ecosystem-contract-check",
        "make scale-readiness-start",
        "make scale-readiness-status",
        "make scale-readiness-progress",
        "make scale-readiness-complete",
        "make metrics-contract-check",
    ]

    banned = [
        "make phase2-start",
        "make phase2-workflow",
        "make phase2-status",
        "make phase2-start-contract",
        "make release-readiness-seed",
        "make phase2-complete",
        "make phase2-progress",
        "make phase2-surface-clarity",
        "make scale-readiness-start",
        "make scale-readiness-status",
        "make scale-readiness-progress",
        "make scale-readiness-complete",
        "make scale-readiness-metrics-contract",
    ]

    for command in required:
        assert command in text

    for command in banned:
        assert command not in text
