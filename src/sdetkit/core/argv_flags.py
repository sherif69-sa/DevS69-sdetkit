from __future__ import annotations

from collections.abc import Sequence


def extract_global_flag(argv: Sequence[str], flag: str) -> tuple[list[str], bool]:
    args = list(argv)
    found = False
    filtered: list[str] = []
    for token in args:
        if token == flag:
            found = True
            continue
        filtered.append(token)
    return filtered, found
