from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import weekly_review as wr


def test_validate_signals_rejects_bad_types() -> None:
    with pytest.raises(ValueError):
        wr._validate_signals({"traffic": "x", "stars": 1, "discussions": 1, "blocker_fixes": 1})


def test_emit_pack_variants(tmp_path: Path) -> None:
    review2 = wr.build_weekly_review(
        tmp_path, week=2, signals={"traffic": 1, "stars": 2, "discussions": 3, "blocker_fixes": 4}
    )
    files2 = wr._emit_pack(tmp_path, "artifacts/w2", review2)
    assert len(files2) == 3

    review3 = wr.build_weekly_review(
        tmp_path,
        week=3,
        signals={"traffic": 10, "stars": 20, "discussions": 30, "blocker_fixes": 40},
        previous_signals={"traffic": 8, "stars": 18, "discussions": 27, "blocker_fixes": 35},
    )
    files3 = wr._emit_pack(tmp_path, "artifacts/w3", review3)
    assert len(files3) == 4

    review1 = wr.build_weekly_review(tmp_path, week=1)
    assert wr._emit_pack(tmp_path, "artifacts/w1", review1) == []


def test_main_markdown_output_to_file_and_strict_signal_failure(tmp_path: Path) -> None:
    sig = tmp_path / "signals.json"
    prev = tmp_path / "prev.json"
    sig.write_text(
        json.dumps({"traffic": 5, "stars": 6, "discussions": 7, "blocker_fixes": 8}),
        encoding="utf-8",
    )
    prev.write_text(
        json.dumps({"traffic": 1, "stars": 2, "discussions": 3, "blocker_fixes": 4}),
        encoding="utf-8",
    )

    out = tmp_path / "out.md"
    rc = wr.main(
        [
            "--root",
            str(tmp_path),
            "--week",
            "3",
            "--signals-file",
            str(sig),
            "--previous-signals-file",
            str(prev),
            "--format",
            "markdown",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    assert out.exists()

    rc_missing = wr.main(["--root", str(tmp_path), "--week", "2", "--strict", "--format", "json"])
    assert rc_missing == 1
