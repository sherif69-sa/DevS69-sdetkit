from __future__ import annotations

from pathlib import Path

MAKEFILE = Path("Makefile")
README = Path("README.md")
OPS_DOC = Path("docs/real-workflow-operations.md")


def test_makefile_exposes_real_workflow_targets() -> None:
    text = MAKEFILE.read_text()

    required_targets = (
        "real-workflow-daily:",
        "real-workflow-daily-fast:",
        "real-workflow-weekly:",
        "real-workflow-premerge:",
        "real-workflow-premerge-fast:",
        "release-room-fast:",
        "ship-readiness-fast:",
        "real-workflow:",
        "ops-daily:",
        "ops-daily-fast:",
        "ops-weekly:",
        "ops-premerge:",
        "ops-premerge-fast:",
        "ops-premerge-next:",
        "ops-premerge-next-fast:",
        "ops-followup:",
        "ops-followup-contract:",
        "ops-now:",
        "ops-now-lite:",
        "ops-next:",
        "ops-workflow:",
    )
    for target in required_targets:
        assert target in text


def test_readme_links_real_workflow_and_ops_aliases() -> None:
    text = README.read_text()

    assert "docs/real-workflow-operations.md" in text
    assert "make ops-daily" in text
    assert "make ops-daily-fast" in text
    assert "make ops-weekly" in text
    assert "make ops-premerge" in text
    assert "make ops-premerge-fast" in text
    assert "make ops-premerge-next" in text
    assert "make ops-premerge-next-fast" in text
    assert "make ops-followup" in text
    assert "make ops-now" in text
    assert "make ops-now-lite" in text
    assert "make ops-next" in text


def test_ops_doc_contains_real_and_alias_commands() -> None:
    text = OPS_DOC.read_text()

    assert "make real-workflow-daily" in text
    assert "make ops-daily-fast" in text
    assert "make real-workflow-weekly" in text
    assert "make real-workflow-premerge" in text
    assert "make ops-daily" in text
    assert "make ops-weekly" in text
    assert "make ops-premerge" in text
    assert "make ops-premerge-fast" in text
    assert "make ops-premerge-next" in text
    assert "make ops-premerge-next-fast" in text
    assert "make ops-followup" in text
    assert "make ops-followup-contract" in text
    assert "make ops-now" in text
    assert "make ops-now-lite" in text
    assert "make ops-next" in text
    assert "build/ops/followup-history.jsonl" in text
    assert "build/ops/followup-history-rollup.json" in text
    assert "docs/ops-followup-schema.v1.json" in text
