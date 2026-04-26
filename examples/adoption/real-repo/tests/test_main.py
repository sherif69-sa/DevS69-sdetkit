from __future__ import annotations

import pytest
from app.main import add


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (2, 3, 5),
        (0, 0, 0),
        (-2, -3, -5),
        (-2, 5, 3),
    ],
)
def test_add(a: int, b: int, expected: int) -> None:
    assert add(a, b) == expected
