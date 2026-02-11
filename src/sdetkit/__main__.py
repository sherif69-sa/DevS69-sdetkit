from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .atomicio import atomic_write_text
from .security import SecurityError, default_http_timeout, ensure_allowed_scheme, safe_path


def _cassette_get(argv: list[str]) -> int:
    import httpx

    from .cassette import Cassette, CassetteRecordTransport, CassetteReplayTransport

    ap = argparse.ArgumentParser(prog="sdetkit cassette-get")
    ap.add_argument("url")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--record", metavar="PATH")
    g.add_argument("--replay", metavar="PATH")
    ap.add_argument("--timeout", type=float, default=None)
    ap.add_argument("--allow-scheme", action="append", default=None)
    ap.add_argument("--follow-redirects", action="store_true")
    ap.add_argument("--no-follow-redirects", dest="follow_redirects", action="store_false")
    ap.set_defaults(follow_redirects=False)
    ap.add_argument("--insecure", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--allow-absolute-path", action="store_true")
    ns = ap.parse_args(argv)

    allowed = {"http", "https"}
    for s in ns.allow_scheme or []:
        allowed.add(str(s).strip().lower())
    try:
        ensure_allowed_scheme(ns.url, allowed=allowed)
    except SecurityError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if ns.insecure:
        print("warning: TLS verification disabled (--insecure)", file=sys.stderr)

    client_opts = {
        "timeout": default_http_timeout(ns.timeout),
        "follow_redirects": bool(ns.follow_redirects),
        "verify": not bool(ns.insecure),
    }

    if ns.replay:
        try:
            replay_path = safe_path(
                Path.cwd(), ns.replay, allow_absolute=True
            )
            cass = Cassette.load(replay_path)
        except (SecurityError, ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        transport = CassetteReplayTransport(cass)
        with httpx.Client(transport=transport, **client_opts) as client:
            r = client.get(ns.url)
            r.raise_for_status()
            sys.stdout.write(json.dumps(r.json(), ensure_ascii=True))
        f = getattr(transport, "assert_exhausted", None)
        if callable(f):
            f()
        return 0

    if ns.record:
        try:
            record_path = safe_path(
                Path.cwd(), ns.record, allow_absolute=True
            )
            if record_path.exists() and not ns.force:
                print("refusing to overwrite existing cassette (use --force)", file=sys.stderr)
                return 2
        except SecurityError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        cass = Cassette()
        inner = httpx.HTTPTransport()
        transport = CassetteRecordTransport(cass, inner)
        with httpx.Client(transport=transport, **client_opts) as client:
            r = client.get(ns.url)
            r.raise_for_status()
            sys.stdout.write(json.dumps(r.json(), ensure_ascii=True))
        payload = json.dumps(cass.to_json(), ensure_ascii=True, sort_keys=True, indent=2) + "\n"
        atomic_write_text(record_path, payload)
        return 0

    with httpx.Client(**client_opts) as client:
        r = client.get(ns.url)
        r.raise_for_status()
        sys.stdout.write(json.dumps(r.json(), ensure_ascii=True))
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "cassette-get":
        try:
            return _cassette_get(argv[1:])
        except Exception as e:
            print(str(e), file=sys.stderr)
            return 2

    from .cli import main as cli_main

    return int(cli_main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
