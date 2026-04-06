"""Tiny module used by the adoption fixture tests."""


def add(a: int, b: int) -> int:
    """Return a deterministic sum for fixture tests."""
    return a + b
