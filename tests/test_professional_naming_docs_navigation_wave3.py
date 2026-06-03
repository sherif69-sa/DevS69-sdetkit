from __future__ import annotations

from pathlib import Path

CANONICAL_ACTIVE_DOCS = [
    Path("docs/integrations-example-asset.md"),
    Path("docs/integrations-example-asset2.md"),
    Path("docs/integrations-platform-readiness-kickoff-workflow.md"),
    Path("docs/integrations-platform-readiness-wrap-publication-workflow.md"),
    Path("docs/integrations-baseline-hardening.md"),
    Path("docs/integrations-baseline-wrap.md"),
    Path("docs/integrations-release-readiness-kickoff.md"),
    Path("docs/integrations-release-readiness-hardening-workflow.md"),
    Path("docs/integrations-platform-readiness-preplan-workflow.md"),
    Path("docs/integrations-release-readiness-wrap-handoff.md"),
]

RETIRED_ACTIVE_DOCS = [
    Path("docs/integrations-demo-asset.md"),
    Path("docs/integrations-demo-asset2.md"),
    Path("docs/integrations-quality-governance-kickoff-workflow.md"),
    Path("docs/integrations-publication-readiness-workflow.md"),
    Path("docs/integrations-phase1-hardening.md"),
    Path("docs/integrations-phase1-wrap.md"),
    Path("docs/integrations-phase2-kickoff.md"),
    Path("docs/integrations-workflow-readiness-hardening-workflow.md"),
    Path("docs/integrations-quality-governance-preplanning-workflow.md"),
    Path("docs/integrations-phase2-wrap-handoff-completion.md"),
]

LEGACY_ACTIVE_TOKENS = (
    "Phase-1",
    "Phase-2",
    "Phase-3",
    "phase1-",
    "phase2-",
    "phase3-",
    "integrations-phase",
    "demo-asset",
    "demo-asset2",
)


def test_canonical_active_docs_pages_exist() -> None:
    for path in CANONICAL_ACTIVE_DOCS:
        assert path.exists(), path


def test_retired_active_docs_pages_are_not_kept_as_live_pages() -> None:
    for path in RETIRED_ACTIVE_DOCS:
        assert not path.exists(), path


def test_canonical_active_docs_pages_do_not_reintroduce_legacy_tokens() -> None:
    for path in CANONICAL_ACTIVE_DOCS:
        text = path.read_text(encoding="utf-8")
        for token in LEGACY_ACTIVE_TOKENS:
            assert token not in text, f"{path} contains {token!r}"


def test_active_navigation_files_do_not_point_to_retired_integration_pages() -> None:
    checked = [
        Path("README.md"),
        Path("docs/index.md"),
        Path("docs/top-10-github-strategy.md"),
        Path("mkdocs.yml"),
    ]

    retired_refs = [path.as_posix() for path in RETIRED_ACTIVE_DOCS]
    for path in checked:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for ref in retired_refs:
            assert ref not in text, f"{path} still points to {ref}"
