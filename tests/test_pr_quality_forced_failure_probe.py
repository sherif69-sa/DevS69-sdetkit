from __future__ import annotations

SENTINEL = "PR_QUALITY_FORCED_FAILURE_V1"
EXPECTED = "review-experience-ready"
OBSERVED = "forced-diagnostic-failure"


def test_forced_pr_quality_diagnostic_signal() -> None:
    """Emit one deterministic failure for PR Quality diagnosis validation."""
    assert OBSERVED == EXPECTED, (
        f"{SENTINEL}: "
        f"expected={EXPECTED!r}; observed={OBSERVED!r}; "
        "the gate must expose the workflow, job, step, test node id, "
        "source file, source line, assertion message, reproduction command, "
        "and direct GitHub job link"
    )
