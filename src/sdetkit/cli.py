from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import apiget, kvcli


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit", add_help=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("kv")
    sub.add_parser("apiget")

    ns, rest = p.parse_known_args(argv)

    if ns.cmd == "kv":
        return kvcli.main(rest)
    if ns.cmd == "apiget":
        return apiget.main(rest)

    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
