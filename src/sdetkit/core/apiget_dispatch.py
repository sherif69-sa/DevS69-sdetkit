from __future__ import annotations

import os
from collections.abc import Callable, Sequence


def run_apiget_with_cassette(
    argv: Sequence[str],
    *,
    cassette: str | None,
    cassette_mode: str | None,
    run_module_main: Callable[[str, Sequence[str]], int],
) -> int:
    rest = list(argv[1:])
    mode = cassette_mode or "auto"

    clean: list[str] = []
    it = iter(rest)
    for arg in it:
        if arg.startswith("--cassette="):
            continue
        if arg == "--cassette":
            next(it, None)
            continue
        if arg.startswith("--cassette-mode="):
            continue
        if arg == "--cassette-mode":
            next(it, None)
            continue
        clean.append(arg)
    rest = clean

    if not cassette:
        return run_module_main("sdetkit.apiget", rest)

    old_cassette = os.environ.get("SDETKIT_CASSETTE")
    old_mode = os.environ.get("SDETKIT_CASSETTE_MODE")
    try:
        os.environ["SDETKIT_CASSETTE"] = str(cassette)
        os.environ["SDETKIT_CASSETTE_MODE"] = str(mode)
        return run_module_main("sdetkit.apiget", rest)
    finally:
        if old_cassette is None:
            os.environ.pop("SDETKIT_CASSETTE", None)
        else:
            os.environ["SDETKIT_CASSETTE"] = old_cassette
        if old_mode is None:
            os.environ.pop("SDETKIT_CASSETTE_MODE", None)
        else:
            os.environ["SDETKIT_CASSETTE_MODE"] = old_mode
