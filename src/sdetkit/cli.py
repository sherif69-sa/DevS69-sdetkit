from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from . import apiget, kvcli, patch, repo


def _add_apiget_args(p: argparse.ArgumentParser) -> None:
    apiget._add_apiget_args(p)

    p.add_argument("--cassette", default=None, help="Cassette file path (enables record/replay).")
    p.add_argument(
        "--cassette-mode",
        choices=["auto", "record", "replay"],
        default=None,
        help="Cassette mode: auto, record, or replay.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    import sys

    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] == "cassette-get":
        from .__main__ import _cassette_get

        try:
            return _cassette_get(argv[1:])
        except Exception as e:
            print(str(e), file=sys.stderr)
            return 2

    if argv and argv[0] == "doctor":
        from .doctor import main as _doctor_main

        return _doctor_main(argv[1:])

    if argv and argv[0] == "patch":
        return patch.main(list(argv[1:]))

    if argv and argv[0] == "repo":
        return repo.main(list(argv[1:]))

    p = argparse.ArgumentParser(prog="sdetkit", add_help=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    kv = sub.add_parser("kv")
    kv.add_argument("args", nargs=argparse.REMAINDER)

    ag = sub.add_parser("apiget")
    _add_apiget_args(ag)

    doc = sub.add_parser("doctor")
    doc.add_argument("args", nargs=argparse.REMAINDER)

    pg = sub.add_parser("patch")
    pg.add_argument("args", nargs=argparse.REMAINDER)

    cg = sub.add_parser("cassette-get")
    cg.add_argument("args", nargs=argparse.REMAINDER)

    rp = sub.add_parser("repo")
    rp.add_argument("args", nargs=argparse.REMAINDER)

    ns = p.parse_args(argv)

    if ns.cmd == "kv":
        return kvcli.main(ns.args)

    if ns.cmd == "patch":
        return patch.main(ns.args)

    if ns.cmd == "repo":
        return repo.main(ns.args)

    if ns.cmd == "apiget":
        raw_args = list(argv)
        rest = raw_args[1:]
        cassette = getattr(ns, "cassette", None)
        cassette_mode = getattr(ns, "cassette_mode", None) or "auto"
        clean: list[str] = []
        it = iter(rest)
        for a in it:
            if a.startswith("--cassette="):
                continue
            if a == "--cassette":
                next(it, None)
                continue
            if a.startswith("--cassette-mode="):
                continue
            if a == "--cassette-mode":
                next(it, None)
                continue
            clean.append(a)
        rest = clean
        if not cassette:
            return apiget.main(rest)
        old_cassette = os.environ.get("SDETKIT_CASSETTE")
        old_mode = os.environ.get("SDETKIT_CASSETTE_MODE")
        try:
            os.environ["SDETKIT_CASSETTE"] = str(cassette)
            os.environ["SDETKIT_CASSETTE_MODE"] = str(cassette_mode)
            return apiget.main(rest)
        finally:
            if old_cassette is None:
                os.environ.pop("SDETKIT_CASSETTE", None)
            else:
                os.environ["SDETKIT_CASSETTE"] = old_cassette
            if old_mode is None:
                os.environ.pop("SDETKIT_CASSETTE_MODE", None)
            else:
                os.environ["SDETKIT_CASSETTE_MODE"] = old_mode
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
