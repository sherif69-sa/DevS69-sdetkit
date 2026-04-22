from __future__ import annotations

from pathlib import Path

from sdetkit.checks.base import CheckContext, normalize_ids


def test_check_context_resolve_and_artifact_path(tmp_path: Path) -> None:
    ctx = CheckContext(repo_root=tmp_path, out_dir=tmp_path / "out")
    assert ctx.resolve("a", "b.txt") == tmp_path / "a" / "b.txt"
    assert ctx.artifact_path("result.json") == tmp_path / "out" / "result.json"


def test_normalize_ids_strips_and_deduplicates() -> None:
    assert normalize_ids([" lint ", "", "lint", " tests "]) == ("lint", "tests")
