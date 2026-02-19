from __future__ import annotations

from pathlib import Path

from sdetkit import docs_qa


def test_docs_qa_passes_repo_docs() -> None:
    report = docs_qa.run_docs_qa(Path('.').resolve())
    assert report.files_checked >= 2
    assert report.links_checked >= 10
    assert report.ok


def test_docs_qa_detects_missing_anchor(tmp_path: Path) -> None:
    (tmp_path / 'README.md').write_text('# Title\n\n[bad](#missing)\n', encoding='utf-8')
    (tmp_path / 'docs').mkdir()
    report = docs_qa.run_docs_qa(tmp_path)
    assert not report.ok
    assert any('missing local anchor' in issue.message for issue in report.issues)
