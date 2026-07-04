from __future__ import annotations

from pathlib import Path


def test_vitest_fixture_contains_failed_typescript_test_path() -> None:
    text = (Path(__file__).parent / "fixtures" / "ci_failures" / "vitest" / "ci_log.txt").read_text(
        encoding="utf-8"
    )

    assert "vitest run" in text
    assert "src/cart-total.test.tsx" in text
    assert "Process completed with exit code 1" in text
