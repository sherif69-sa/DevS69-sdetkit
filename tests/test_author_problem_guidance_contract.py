from __future__ import annotations

from pathlib import Path

from sdetkit import author_problem


def test_author_problem_guidance_uses_actionable_novelty_language() -> None:
    assert author_problem._NOVELTY_REVIEW_SOURCES == (
        "issues",
        "PRs",
        "releases",
        "docs",
        "discussions",
    )
    assert author_problem._NOVELTY_REVIEW_GUIDANCE == (
        "- Verify novelty against issues, PRs, releases, docs, and discussions "
        "before accepting a candidate."
    )


def test_author_problem_guidance_is_named_instead_of_inline_task_marker() -> None:
    text = Path("src/sdetkit/author_problem.py").read_text(encoding="utf-8")

    assert "_NOVELTY_REVIEW_GUIDANCE" in text
    assert "TODO: compare against issues" not in text


def test_author_problem_source_does_not_emit_unresolved_task_markers() -> None:
    text = Path("src/sdetkit/author_problem.py").read_text(encoding="utf-8")

    forbidden = "TO" + "DO"
    assert forbidden not in text
