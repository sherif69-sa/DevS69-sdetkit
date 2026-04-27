from __future__ import annotations

import re
from pathlib import Path


def test_integration_closeout_docs_do_not_contain_lane_typo() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    pattern = re.compile(r"\blane\s+lane\b", re.IGNORECASE)
    for path in sorted((repo_root / "docs").glob("**/*.md")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(repo_root)}:{line_no}")
    assert not offenders, "Found 'Lane lane' typo in:\n" + "\n".join(offenders)


def test_docs_do_not_contain_accidental_duplicate_words() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    duplicate_word_pattern = re.compile(r"\b([A-Za-z][A-Za-z-]{2,})\s+\1\b")
    inline_code_pattern = re.compile(r"`[^`]*`")

    allowlist = {
        # CLI syntax examples can intentionally repeat flag names in code spans.
        "waivers waivers",
    }

    for path in sorted((repo_root / "docs").glob("**/*.md")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            normalized = inline_code_pattern.sub(" __code__ ", line).strip().lower()
            if not normalized:
                continue
            if normalized in allowlist:
                continue
            if duplicate_word_pattern.search(normalized):
                offenders.append(f"{path.relative_to(repo_root)}:{line_no}")
    assert not offenders, "Found duplicate words in docs:\n" + "\n".join(offenders)
