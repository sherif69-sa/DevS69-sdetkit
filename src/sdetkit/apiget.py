from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
    p.add_argument("--method", default="GET")
    p.add_argument("--header", action="append", default=None)
    p.add_argument("--data", default=None)
    p.add_argument("--json", dest="json_data", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--query", action="append", default=None)

    ns = p.parse_args(argv)

    def _read_at_file(v: str) -> str:
        if not v.startswith("@"):
            return v
        if v == "@-":
            try:
                return sys.stdin.read()
            except Exception as err:
                raise ValueError("could not read stdin") from err
        path = v[1:]
        try:
            return Path(path).read_text(encoding="utf-8")
        except FileNotFoundError as err:
            raise ValueError(f"file not found: {path}") from err
        except OSError as err:
            raise ValueError(f"could not read file: {path}") from err

    _q = getattr(ns, "query", None)
    if _q:
        extra: list[tuple[str, str]] = []
        for _item in _q:
            _item = str(_item)
            if "=" not in _item:
                _die("query must be KEY=VALUE")
            _k, _v = _item.split("=", 1)
            if _k == "":
                _die("query must be KEY=VALUE")
            extra.append((_k, _v))
        sp = urlsplit(str(ns.url))
        base = parse_qsl(sp.query, keep_blank_values=True)
        q = urlencode(base + extra, doseq=True)
        ns.url = urlunsplit((sp.scheme, sp.netloc, sp.path, q, sp.fragment))

    _req_method = str(getattr(ns, "method", "GET")).upper() or "GET"
    _req_headers: dict[str, str] = {}
    _hdrs = getattr(ns, "header", None)
    if _hdrs:
        for _h in _hdrs:
            _h = str(_h)
            if _h.startswith("@"):
                _txt = _read_at_file(_h)
                for _ln in _txt.splitlines():
                    _ln = _ln.strip()
                    if _ln == "" or _ln.startswith("#"):
                        continue
                    if ":" not in _ln:
                        _die("header must be KEY:VALUE")
                    _k, _v = _ln.split(":", 1)
                    _req_headers[_k.strip()] = _v.lstrip()
                continue
            if ":" not in _h:
                _die("header must be KEY:VALUE")
            _k, _v = _h.split(":", 1)
            _req_headers[_k.strip()] = _v.lstrip()
    _req_content: bytes | None = None
    _req_json: object | None = None
    _data = getattr(ns, "data", None)
    _json_data = getattr(ns, "json_data", None)
    try:
        if _data is not None:
            _data = _read_at_file(str(_data))
        if _json_data is not None:
            _json_data = _read_at_file(str(_json_data))
    except ValueError as e:
        sys.stderr.write(str(e).rstrip() + "\n")
        return 1
    if _data is not None and _json_data is not None:
        _die("use only one of: --data, --json")
    if _data is not None:
        _req_content = str(_data).encode("utf-8")
    if _json_data is not None:
        try:
            _req_json = json.loads(str(_json_data))
        except ValueError:
            _die("invalid JSON for --json")
    if ns.paginate and (_req_method != "GET" or _req_content is not None or _req_json is not None):
        _die("paginate only supports GET without a request body")

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
        cassette_path = os.getenv("SDETKIT_CASSETTE")
        cassette_mode = os.getenv("SDETKIT_CASSETTE_MODE", "auto")
        transport = None
        if cassette_path:
            from .cassette import open_transport

            upstream_transport = httpx.HTTPTransport() if cassette_mode == "record" else None
            transport = open_transport(cassette_path, cassette_mode, upstream=upstream_transport)
        with httpx.Client() if transport is None else httpx.Client(transport=transport) as raw:
            c = SdetHttpClient(raw, retry=pol, trace_header=ns.trace_header)

            data: object

            if ns.paginate:
                if (
                    _req_method == "GET"
                    and _req_content is None
                    and _req_json is None
                    and not _req_headers
                ):
                    data = c.get_json_list_paginated(
                        ns.url,
                        max_pages=ns.max_pages,
                        request_id=ns.request_id,
                        timeout=ns.timeout,
                    )
                else:
                    resp = raw.request(
                        _req_method,
                        ns.url,
                        headers=_req_headers or None,
                        content=_req_content,
                        json=_req_json,
                        timeout=ns.timeout,
                    )
                    resp.raise_for_status()
                    data = resp.json()
            else:
                if (
                    _req_method != "GET"
                    or _req_content is not None
                    or _req_json is not None
                    or _req_headers
                ):
                    resp = raw.request(
                        _req_method,
                        ns.url,
                        headers=_req_headers or None,
                        content=_req_content,
                        json=_req_json,
                        timeout=ns.timeout,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    if ns.expect == "dict" and not isinstance(data, dict):
                        raise ValueError("expected dict")
                    if ns.expect == "list" and not isinstance(data, list):
                        raise ValueError("expected list")
                    if ns.expect == "any" and not isinstance(data, (dict, list)):
                        raise ValueError("expected dict or list")
                else:
                    if ns.expect == "dict":
                        data = c.get_json_dict(ns.url, request_id=ns.request_id, timeout=ns.timeout)
                    elif ns.expect == "list":
                        data = c.get_json_list(ns.url, request_id=ns.request_id, timeout=ns.timeout)
                    else:
                        try:
                            data = c.get_json_dict(
                                ns.url, request_id=ns.request_id, timeout=ns.timeout
                            )
                        except ValueError:
                            data = c.get_json_list(
                                ns.url, request_id=ns.request_id, timeout=ns.timeout
                            )
        out_s = json.dumps(data, sort_keys=True, indent=2 if ns.pretty else None) + "\n"
        out_path = getattr(ns, "out", None)
        if out_path:
            pp = Path(str(out_path))
            pp.parent.mkdir(parents=True, exist_ok=True)
            pp.write_text(out_s, encoding="utf-8")
        else:
            sys.stdout.write(out_s)
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
    except (RuntimeError, AssertionError) as e:
        sys.stderr.write(str(e).rstrip() + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
