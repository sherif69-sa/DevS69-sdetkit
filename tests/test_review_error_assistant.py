from __future__ import annotations

from sdetkit.review_engine import triage_error_log


def test_triage_error_log_maps_common_failures_to_recommendations() -> None:
    sample = """
I001 [*] Import block is un-sorted or un-formatted
F401 [*] imported but unused
"""
    payload = triage_error_log(sample)
    ids = {row["id"] for row in payload["matched_rules"]}
    assert "ruff-import-order" in ids
    assert "ruff-unused-import" in ids
    assert payload["summary"]["ok"] is False
