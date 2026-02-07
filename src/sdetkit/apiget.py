from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

import httpx

from .netclient import CircuitOpenError, RetryPolicy, SdetHttpClient


def _die(msg: str) -> None:
    sys.stderr.write(msg.rstrip() + "\n")
    raise SystemExit(2)


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit apiget", add_help=True)
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
    ns = p.parse_args(argv)

    if ns.retries < 1:
        _die("retries must be >= 1")
    if ns.max_pages < 1:
        _die("max_pages must be >= 1")
    if ns.paginate and ns.expect == "dict":
        _die("paginate requires --expect list (or any)")

    pol = RetryPolicy(
        retries=ns.retries,
        retry_on_429=ns.retry_429,
        backoff_base=0.5,
        backoff_factor=2.0,
        backoff_jitter=0.0,
    )

    try:
        with httpx.Client() as raw:
            c = SdetHttpClient(raw, retry=pol, trace_header=ns.trace_header)

            data: object

            if ns.paginate:
                data = c.get_json_list_paginated(
                    ns.url,
                    max_pages=ns.max_pages,
                    request_id=ns.request_id,
                    timeout=ns.timeout,
                )
            else:
                if ns.expect == "dict":
                    data = c.get_json_dict(ns.url, request_id=ns.request_id, timeout=ns.timeout)
                elif ns.expect == "list":
                    data = c.get_json_list(ns.url, request_id=ns.request_id, timeout=ns.timeout)
                else:
                    try:
                        data = c.get_json_dict(ns.url, request_id=ns.request_id, timeout=ns.timeout)
                    except ValueError:
                        data = c.get_json_list(ns.url, request_id=ns.request_id, timeout=ns.timeout)

        out = json.dumps(data, sort_keys=True, indent=2 if ns.pretty else None)
        sys.stdout.write(out + "\n")
        return 0

    except TimeoutError:
        sys.stderr.write("request timed out\n")
        return 1
    except CircuitOpenError:
        sys.stderr.write("circuit open\n")
        return 1
    except ValueError as e:
        sys.stderr.write(str(e).rstrip() + "\n")
        return 1
    except RuntimeError as e:
        sys.stderr.write(str(e).rstrip() + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
