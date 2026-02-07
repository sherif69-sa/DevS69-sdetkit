from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import apiget, kvcli


def _add_apiget_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("url")
    p.add_argument("--expect", choices=["any", "dict", "list"], default="any")
    p.add_argument("--paginate", action="store_true")
    p.add_argument("--max-pages", type=int, default=100)
    p.add_argument("--retries", type=int, default=1)
    p.add_argument("--retry-429", action="store_true")
    p.add_argument("--timeout", type=float, default=None)
    p.add_argument("--trace-header", default=None)
    p.add_argument("--request-id", default=None)
    p.add_argument("--pretty", action="store_true")


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit", add_help=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    kv = sub.add_parser("kv")
    kv.add_argument("args", nargs=argparse.REMAINDER)

    ag = sub.add_parser("apiget")
    _add_apiget_args(ag)

    ns = p.parse_args(argv)

    if ns.cmd == "kv":
        return kvcli.main(ns.args)

    if ns.cmd == "apiget":
        rest: list[str] = [
            ns.url,
            "--expect",
            ns.expect,
            "--max-pages",
            str(ns.max_pages),
            "--retries",
            str(ns.retries),
        ]

        if ns.paginate:
            rest.append("--paginate")
        if ns.retry_429:
            rest.append("--retry-429")
        if ns.timeout is not None:
            rest.extend(["--timeout", str(ns.timeout)])
        if ns.trace_header is not None:
            rest.extend(["--trace-header", str(ns.trace_header)])
        if ns.request_id is not None:
            rest.extend(["--request-id", str(ns.request_id)])
        if ns.pretty:
            rest.append("--pretty")

        return apiget.main(rest)

    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
