from __future__ import annotations

import sys
from collections.abc import Callable, Sequence


def dispatch_release_subcommand(
    args: Sequence[str],
    *,
    run_module_main: Callable[[str, Sequence[str]], int],
) -> int:
    if not args:
        sys.stderr.write(
            "release error: expected subcommand (gate|doctor|security|evidence|repo)\n"
        )
        return 2
    subcmd = args[0]
    rest = list(args[1:])
    if subcmd == "gate":
        return run_module_main("sdetkit.gate", rest)
    if subcmd == "doctor":
        return run_module_main("sdetkit.doctor", rest)
    if subcmd == "security":
        return run_module_main("sdetkit.security_gate", rest)
    if subcmd == "evidence":
        return run_module_main("sdetkit.evidence", rest)
    if subcmd == "repo":
        return run_module_main("sdetkit.repo", rest)
    sys.stderr.write(
        "release error: supported subcommands are gate|doctor|security|evidence|repo\n"
    )
    return 2
