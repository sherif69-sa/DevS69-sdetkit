from __future__ import annotations

from sdetkit.proof_runtime_guard import (
    CLAIMED_WRITE,
    CLEAN,
    EVIDENCE_SHADOW,
    RESERVED_EVIDENCE_PATHS,
    RUNTIME_GUARD_VIOLATION,
    UNCLAIMED_WRITE,
    assess_runtime_guard,
    render_markdown,
)


def test_runtime_guard_accepts_clean_execution_without_authority() -> None:
    result = assess_runtime_guard(
        expected_changed_files=["src/sdetkit/example.py"],
        mutated_files=[],
        reserved_evidence_changed_files=[],
    )

    assert result["status"] == CLEAN
    assert result[RUNTIME_GUARD_VIOLATION] is False
    assert result["proof_result_allowed"] is True
    assert result["boundary"]["automation_allowed"] is False
    assert result["boundary"]["merge_authorized"] is False


def test_runtime_guard_classifies_claimed_workspace_write() -> None:
    result = assess_runtime_guard(
        expected_changed_files=["src/sdetkit/example.py"],
        mutated_files=["src/sdetkit/example.py"],
        reserved_evidence_changed_files=[],
    )

    assert result["status"] == CLAIMED_WRITE
    assert result["claimed_mutated_files"] == ["src/sdetkit/example.py"]
    assert result[RUNTIME_GUARD_VIOLATION] is True
    assert result["proof_result_allowed"] is False


def test_runtime_guard_rejects_write_outside_expected_inventory() -> None:
    result = assess_runtime_guard(
        expected_changed_files=["src/sdetkit/example.py"],
        mutated_files=["src/sdetkit/injected.py"],
        reserved_evidence_changed_files=[],
    )

    assert result["status"] == UNCLAIMED_WRITE
    assert result["unclaimed_mutated_files"] == ["src/sdetkit/injected.py"]
    assert result[RUNTIME_GUARD_VIOLATION] is True


def test_runtime_guard_rejects_reserved_evidence_shadowing() -> None:
    result = assess_runtime_guard(
        expected_changed_files=["src/sdetkit/example.py"],
        mutated_files=[],
        reserved_evidence_changed_files=[RESERVED_EVIDENCE_PATHS[0]],
    )

    assert result["status"] == EVIDENCE_SHADOW
    assert result["reserved_evidence_shadowed_files"] == [RESERVED_EVIDENCE_PATHS[0]]
    assert result[RUNTIME_GUARD_VIOLATION] is True


def test_runtime_guard_markdown_states_detection_only_boundary() -> None:
    markdown = render_markdown(
        assess_runtime_guard(
            expected_changed_files=["src/sdetkit/example.py"],
            mutated_files=["src/sdetkit/injected.py"],
            reserved_evidence_changed_files=[],
        )
    )

    assert "Status: `unclaimed_write`" in markdown
    assert "Runtime guard violation: `true`" in markdown
    assert "External filesystem containment enforced: `false`" in markdown
    assert "Process escape prevention enforced: `false`" in markdown
    assert "Automation allowed: `false`" in markdown
