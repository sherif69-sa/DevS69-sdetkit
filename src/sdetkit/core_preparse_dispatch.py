from __future__ import annotations

import sys
from collections.abc import Sequence


def dispatch_core_preparse(argv: Sequence[str]) -> int | None:
    if not argv:
        return None

    if argv[0] == "cassette-get":
        from .__main__ import _cassette_get

        try:
            return _cassette_get(list(argv[1:]))
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 2

    if argv[0] == "doctor":
        from .doctor import main as _doctor_main

        return _doctor_main(list(argv[1:]))

    if argv[0] == "gate":
        from .gate import main as _gate_main

        return _gate_main(list(argv[1:]))

    if argv[0] == "ci":
        from .ci import main as _ci_main

        return _ci_main(list(argv[1:]))

    return None
