from __future__ import annotations

import re
import subprocess
from pathlib import Path


def test_quality_script_unknown_mode_suggests_closest_match() -> None:
    result = subprocess.run(
        ["bash", "quality.sh", "cit"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Did you mean: bash quality.sh ci" in result.stderr


def test_quality_script_help_documents_fast_and_full_lanes() -> None:
    text = Path("quality.sh").read_text(encoding="utf-8")
    assert (
        "Usage: bash quality.sh {all|ci|verify|fmt|lint|type|doctor|test|full-test|cov|mut|muthtml|boost}"
        in text
    )
    assert "Fast/smoke lane for local confidence; not merge truth." in text
    assert "Full verification lane before merge (format, lint, typing, full tests)." in text


def test_quality_script_verify_uses_full_test_path() -> None:
    text = Path("quality.sh").read_text(encoding="utf-8")
    match = re.search(r"verify\)\n(?P<body>.*?run_full_test\n    ;;)", text, re.DOTALL)
    assert match is not None
    body = match.group("body")
    assert "run_fmt_check" in body
    assert "run_lint" in body
    assert "run_type" in body
    assert "run_full_test" in body
    assert "run_gate_fast" not in body
