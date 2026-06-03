from __future__ import annotations

from sdetkit.phases import (
    platform_readiness_kickoff,
    platform_readiness_preplan,
    platform_readiness_wrap_publication,
    release_readiness_hardening,
    release_readiness_wrap_handoff,
)


def test_release_readiness_hardening_active_contract_uses_canonical_names() -> None:
    text = release_readiness_hardening._DEFAULT_PAGE_TEMPLATE

    assert release_readiness_hardening._PAGE_PATH == (
        "docs/integrations-release-readiness-hardening-workflow.md"
    )
    assert "Release Readiness Hardening" in text
    assert "release readiness hardening" in text
    assert "integrations-phase2-hardening-workflow.md" not in text
    assert "Phase-2 hardening" not in text
    assert "phase2-hardening" not in text


def test_platform_readiness_preplan_active_contract_uses_canonical_names() -> None:
    text = platform_readiness_preplan._DEFAULT_PAGE_TEMPLATE

    assert platform_readiness_preplan._PAGE_PATH == (
        "docs/integrations-platform-readiness-preplan-workflow.md"
    )
    assert "Platform Readiness Preplan" in text
    assert "platform readiness preplan" in text
    assert "integrations-phase3-preplan-workflow.md" not in text
    assert "Phase-3 pre-plan" not in text
    assert "phase3-preplan" not in text


def test_release_readiness_wrap_handoff_active_contract_uses_canonical_names() -> None:
    text = release_readiness_wrap_handoff._DEFAULT_PAGE_TEMPLATE

    assert release_readiness_wrap_handoff._PAGE_PATH == (
        "docs/integrations-release-readiness-wrap-handoff.md"
    )
    assert "Release Readiness Wrap Handoff" in text
    assert "release readiness wrap handoff" in text
    assert "Phase-2 wrap + handoff" not in text
    assert "phase2-wrap-handoff" not in text


def test_platform_readiness_kickoff_active_contract_uses_canonical_names() -> None:
    text = platform_readiness_kickoff._DEFAULT_PAGE_TEMPLATE

    assert platform_readiness_kickoff._PAGE_PATH == (
        "docs/integrations-platform-readiness-kickoff-workflow.md"
    )
    assert "platform readiness kickoff" in text
    assert "integrations-phase3-kickoff-workflow.md" not in text
    assert "Phase-3 kickoff" not in text
    assert "phase3-kickoff" not in text


def test_platform_readiness_wrap_publication_active_contract_uses_canonical_names() -> None:
    text = platform_readiness_wrap_publication._DEFAULT_PAGE_TEMPLATE

    assert platform_readiness_wrap_publication._PAGE_PATH == (
        "docs/integrations-platform-readiness-wrap-publication-workflow.md"
    )
    assert "platform readiness wrap publication" in text
    assert "integrations-phase3-wrap-publication-workflow.md" not in text
    assert "Phase-3 wrap publication" not in text
    assert "phase3-wrap-publication" not in text
