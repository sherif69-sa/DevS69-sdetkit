from __future__ import annotations

from scripts.post_impact_pr_comment import MARKER, _compose_comment_body, _find_existing_comment_id, upsert_comment


def test_compose_comment_body_includes_marker() -> None:
    body = _compose_comment_body("hello")
    assert MARKER in body
    assert "hello" in body


def test_find_existing_comment_id_returns_marked_comment() -> None:
    comments = [
        {"id": 10, "body": "random"},
        {"id": 99, "body": f"prefix\n{MARKER}\ncontent"},
    ]
    assert _find_existing_comment_id(comments) == 99


def test_upsert_comment_dry_run_short_circuits_network() -> None:
    status = upsert_comment("owner/repo", 12, "token", "body", dry_run=True)
    assert status == "dry_run"
