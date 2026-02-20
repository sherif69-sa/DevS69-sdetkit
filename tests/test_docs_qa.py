from __future__ import annotations

from pathlib import Path

from sdetkit import docs_qa


def test_docs_qa_passes_repo_docs() -> None:
    report = docs_qa.run_docs_qa(Path(".").resolve())
    assert report.files_checked >= 2
    assert report.links_checked >= 10
    assert report.ok


def test_docs_qa_detects_missing_anchor(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Title\n\n[bad](#missing)\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    report = docs_qa.run_docs_qa(tmp_path)
    assert not report.ok
    assert any("missing local anchor" in issue.message for issue in report.issues)


def test_docs_qa_handles_reference_links_and_duplicate_headings(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Intro\n\n"
        "## Section\n\n"
        "## Section\n\n"
        "[ok-ref][guide]\n\n"
        "[guide]: docs/guide.md#section-1\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\n## Section\n\n## Section\n", encoding="utf-8")

    report = docs_qa.run_docs_qa(tmp_path)
    assert report.ok


def test_docs_qa_ignores_links_inside_fenced_code_blocks(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Intro\n\n```bash\n[broken](docs/missing.md)\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()

    report = docs_qa.run_docs_qa(tmp_path)
    assert report.ok
