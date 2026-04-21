from __future__ import annotations

import sys
from collections.abc import Sequence


def dispatch_core_preparse(argv: Sequence[str]) -> int | None:
    if not argv:
        return None

    if argv[0] == "cassette-get":
        try:
            try:
                from ..__main__ import _cassette_get
            except Exception:  # pragma: no cover - defensive fallback for partial imports
                from ..cassette_get import cassette_get as _cassette_get
            return _cassette_get(list(argv[1:]))
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 2

    if argv[0] == "doctor":
        from ..doctor import main as _doctor_main

        return _doctor_main(list(argv[1:]))

    if argv[0] == "gate":
        from ..gate import main as _gate_main

        return _gate_main(list(argv[1:]))

    if argv[0] == "ci":
        from ..ci import main as _ci_main

        return _ci_main(list(argv[1:]))

    return None
