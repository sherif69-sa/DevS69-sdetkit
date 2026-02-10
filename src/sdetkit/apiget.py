from __future__ import annotations

import argparse
import base64
import json
import os
import shlex
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from .netclient import (
    CircuitOpenError,
    HttpStatusError,
    RetryPolicy,
    SdetHttpClient,
    _link_next_url,
)


def _is_sensitive_header(name: str) -> bool:
    n = name.strip().lower()
    if n in {"authorization", "proxy-authorization", "cookie", "set-cookie"}:
        return True
    if "api-key" in n or "apikey" in n:
        return True
    if "token" in n or "secret" in n or "password" in n:
        return True
    return False


def _redact_header_value(name: str, value: str) -> str:
    if _is_sensitive_header(name):
        return "<redacted>"
    return value


def _merged_headers(client, extra, debug: bool) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for k, v in client.headers.items():
            out[str(k)] = str(v)
    except Exception:
        pass
    if extra:
        try:
            for k, v in dict(extra).items():
                out[str(k)] = str(v)
        except Exception:
            try:
                for k, v in extra.items():
                    out[str(k)] = str(v)
            except Exception:
                if debug:
                    traceback.print_exc()
                pass
    return out


def _verbose_request(
    method: str,
    url: str,
    headers: dict[str, str],
    keep: set[str] | None = None,
) -> None:
    sys.stderr.write(f"http request: {method} {url}\n")

    keep_lc = {k.strip().lower() for k in (keep or set())}
    drop = {"accept", "accept-encoding", "connection", "host", "user-agent"}

    items: list[tuple[str, str]] = []
    for k, v in headers.items():
        kl = k.strip().lower()
        if kl in drop and kl not in keep_lc:
            if kl == "user-agent":
                vv = str(v).strip()
                if vv.lower().startswith("python-httpx/"):
                    continue
                items.append((kl, v))
                continue
            continue
        items.append((kl, v))

    parts = ["curl", "-X", str(method), str(url)]
    for k, v in sorted(items, key=lambda kv: kv[0]):
        parts.extend(["-H", f"{k}: {_redact_header_value(k, v)}"])
    sys.stderr.write("http request curl: " + " ".join(shlex.quote(x) for x in parts) + "\n")

    for k, v in sorted(items, key=lambda kv: kv[0]):
        sys.stderr.write(f"http request header: {k}: {_redact_header_value(k, v)}\n")


def _verbose_response(resp) -> None:
    sys.stderr.write(f"http response: {resp.status_code}\n")
    items = list(resp.headers.items())
    items.sort(key=lambda kv: str(kv[0]).lower())
    for k, v in items:
        kk = str(k)
        vv = _redact_header_value(kk, str(v))
        sys.stderr.write(f"http response header: {kk}: {vv}\n")


def _die(msg: str) -> None:
    sys.stderr.write(msg.rstrip() + "\n")
    raise SystemExit(2)


def _add_apiget_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("url", help="Request URL.")
    p.add_argument(
        "--expect",
        choices=["any", "dict", "list"],
        default="any",
        help="Validate top-level JSON type (any, dict, list).",
    )
    p.add_argument(
        "--paginate",
        action="store_true",
        help="Follow Link: rel=next and concatenate pages.",
    )
    p.add_argument("--max-pages", type=int, default=100, help="Pagination page limit (>= 1).")
    p.add_argument(
        "--retries", type=int, default=1, help="Retry attempts for transient errors (>= 1)."
    )
    p.add_argument("--retry-429", action="store_true", help="Retry HTTP 429 responses.")
    p.add_argument("--timeout", type=float, default=None, help="Request timeout in seconds.")
    p.add_argument(
        "--trace-header",
        default=None,
        help="Header name to include as a trace correlation id.",
    )
    p.add_argument(
        "--request-id",
        default=None,
        help="Override request id value (used with --trace-header).",
    )
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    p.add_argument("--print-status", action="store_true", help="Print HTTP status code to stderr.")
    p.add_argument("--dump-headers", action="store_true", help="Print response headers to stderr.")
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print request/response metadata to stderr (redacting secrets).",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Print debug diagnostics (tracebacks) to stderr.",
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--fail",
        action="store_true",
        help="Fail with rc=1 on HTTP status >= 400 and suppress body.",
    )
    g.add_argument(
        "--fail-with-body",
        action="store_true",
        help="Fail like --fail but still write response body to stdout.",
    )
    p.add_argument("--method", default="GET", help="HTTP method (default: GET).")
    p.add_argument(
        "--header",
        action="append",
        default=None,
        help="Request header (KEY:VALUE) or @file (one KEY:VALUE per line).",
    )
    p.add_argument(
        "--auth",
        default=None,
        help=(
            "Authorization helper: bearer:TOKEN or basic:USER:PASS "
            "(ignored if Authorization header is set)."
        ),
    )
    p.add_argument(
        "--data", default=None, help="Request body bytes from literal, @file, or @- (stdin)."
    )
    p.add_argument(
        "--json",
        dest="json_data",
        default=None,
        help="Request JSON from literal, @file, or @- (stdin).",
    )
    p.add_argument(
        "--query", action="append", default=None, help="Add query param KEY=VALUE (repeatable)."
    )
    p.add_argument("--out", default=None, help="Write JSON output to a file instead of stdout.")


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit apiget", add_help=True)
    _add_apiget_args(p)

    ns = p.parse_args(argv)
    _printed_req = {"v": False}

    class _AtFileError(Exception):
        pass

    def _read_at_file_text(v: str) -> str:
        if not isinstance(v, str):
            return v
        if not v.startswith("@"):
            return v
        path = v[1:]
        if path == "-":
            return sys.stdin.read()
        if path == "":
            raise _AtFileError("apiget: cannot read file: <empty path>")
        try:
            return Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            raise _AtFileError("apiget: file not found: " + path) from None
        except (OSError, UnicodeError):
            raise _AtFileError("apiget: cannot read file: " + path) from None

    def _read_at_file_bytes(v: str) -> bytes | str:
        if not isinstance(v, str):
            return v
        if not v.startswith("@"):
            return v
        path = v[1:]
        if path == "-":
            try:
                b = sys.stdin.buffer.read()
                if isinstance(b, (bytes, bytearray)):
                    return bytes(b)
            except Exception:
                pass
            return sys.stdin.read()
        if path == "":
            raise _AtFileError("apiget: cannot read file: <empty path>")
        try:
            return Path(path).read_bytes()
        except FileNotFoundError:
            raise _AtFileError("apiget: file not found: " + path) from None
        except OSError:
            raise _AtFileError("apiget: cannot read file: " + path) from None

    def _auth_to_header_value(v: str) -> str:
        v = v.strip()
        if v == "" or ":" not in v:
            raise ValueError("auth must be bearer:TOKEN or basic:USER:PASS")
        scheme, rest = v.split(":", 1)
        scheme = scheme.strip().lower()
        rest = rest.strip()
        if scheme == "bearer":
            if rest == "":
                raise ValueError("auth bearer token is required")
            return f"Bearer {rest}"
        if scheme == "basic":
            if ":" not in rest:
                raise ValueError("auth basic credentials must be USER:PASS")
            user, pwd = rest.split(":", 1)
            raw = f"{user}:{pwd}".encode()
            token = base64.b64encode(raw).decode("ascii")
            return f"Basic {token}"
        raise ValueError("auth scheme must be bearer or basic")

    _auth_value: str | None = None
    _auth = getattr(ns, "auth", None)
    if _auth is not None:
        try:
            _auth_value = _auth_to_header_value(str(_auth))
        except ValueError as err:
            _die(str(err))

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
                try:
                    _txt = _read_at_file_text(_h)
                except _AtFileError as e:
                    sys.stderr.write(str(e).rstrip() + "\n")
                    return 1
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
    if _auth_value is not None:
        has_authz = any(k.strip().lower() == "authorization" for k in _req_headers)
        if not has_authz:
            _req_headers["Authorization"] = _auth_value
    _req_content: bytes | None = None
    _req_json: object | None = None
    _data = getattr(ns, "data", None)
    _json_data = getattr(ns, "json_data", None)
    try:
        if _data is not None:
            try:
                _data = _read_at_file_bytes(str(_data))
            except _AtFileError as e:
                sys.stderr.write(str(e).rstrip() + "\n")
                return 1
        if _json_data is not None:
            try:
                _json_data = _read_at_file_text(str(_json_data))
            except _AtFileError as e:
                sys.stderr.write(str(e).rstrip() + "\n")
                return 1
    except ValueError as e:
        if getattr(ns, "verbose", False):
            _raw = locals().get("raw")
            _hdr_src = locals().get("headers") or {}
            try:
                _hdrs = (
                    _merged_headers(_raw, _hdr_src, getattr(ns, "debug", False))
                    if _raw is not None
                    else _hdr_src
                )
            except Exception:
                _hdrs = _hdr_src
            _verbose_request(getattr(ns, "method", "GET"), getattr(ns, "url", ""), _hdrs)
        if getattr(ns, "debug", False):
            traceback.print_exc()
        sys.stderr.write(str(e).rstrip() + "\n")
        return 1
    if _data is not None and _json_data is not None:
        _die("use only one of: --data, --json")
    if _data is not None:
        if isinstance(_data, (bytes, bytearray)):
            _req_content = bytes(_data)
        else:
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
        _client_kwargs: dict[str, object] = {}
        if transport is not None:
            _client_kwargs["transport"] = transport
        with httpx.Client(**_client_kwargs) as raw:
            if getattr(ns, "verbose", False) and callable(getattr(raw, "request", None)):
                _orig_request = raw.request

                def _wrapped_request(method, url, **kwargs):
                    resp = _orig_request(method, url, **kwargs)
                    try:
                        req = getattr(resp, "request", None)
                        if req is not None:
                            _verbose_request(req.method, str(req.url), dict(req.headers))
                        else:
                            _verbose_request(
                                str(method), str(url), dict(kwargs.get("headers") or {})
                            )
                        _printed_req["v"] = True
                    except Exception:
                        pass
                    try:
                        _verbose_response(resp)
                    except Exception:
                        pass
                    return resp

                raw.request = _wrapped_request
            c = SdetHttpClient(raw, retry=pol, trace_header=ns.trace_header)

            def _print_status_and_headers(resp: httpx.Response) -> None:
                if getattr(ns, "print_status", False):
                    sys.stderr.write(f"http status: {resp.status_code}\n")
                if getattr(ns, "dump_headers", False):
                    items = list(resp.headers.multi_items())
                    items.sort(key=lambda kv: (kv[0].lower(), kv[0], kv[1]))
                    for k, v in items:
                        sys.stderr.write(f"http header: {k}: {v}\n")

            def _check_status(resp: httpx.Response) -> None:
                if resp.status_code < 200 or resp.status_code >= 300:
                    raise RuntimeError("non-2xx response")

            data: object

            if ns.paginate:
                if getattr(ns, "dump_headers", False):
                    _die("dump-headers is not supported with --paginate")

                if (
                    getattr(ns, "print_status", False)
                    and _req_method == "GET"
                    and _req_content is None
                    and _req_json is None
                ):
                    out: list = []
                    seen: set[str] = set()
                    cur = str(ns.url)

                    for _ in range(int(ns.max_pages)):
                        resp, page, _rid = c._request_json(
                            cur,
                            headers=_req_headers or None,
                            request_id=ns.request_id,
                            timeout=ns.timeout,
                            retry=None,
                            hook=None,
                            breaker=None,
                        )
                        _print_status_and_headers(resp)
                        if not isinstance(page, list):
                            raise ValueError("expected list")
                        out.extend(page)

                        nxt = _link_next_url(resp)
                        if not nxt:
                            data = out
                            break
                        if nxt in seen:
                            raise RuntimeError("pagination cycle")
                        seen.add(nxt)
                        cur = nxt
                    else:
                        raise RuntimeError("pagination limit exceeded")

                    data = out
                else:
                    data = c.get_json_list_paginated(
                        ns.url,
                        max_pages=ns.max_pages,
                        headers=_req_headers or None,
                        request_id=ns.request_id,
                        timeout=ns.timeout,
                    )

            else:
                needs_raw = (
                    _req_method != "GET"
                    or _req_content is not None
                    or _req_json is not None
                    or getattr(ns, "print_status", False)
                    or getattr(ns, "dump_headers", False)
                    or getattr(ns, "fail", False)
                    or getattr(ns, "fail_with_body", False)
                )

                if needs_raw:
                    resp = c.request(
                        _req_method,
                        ns.url,
                        headers=_req_headers or None,
                        request_id=ns.request_id,
                        content=_req_content,
                        json=_req_json,
                        timeout=ns.timeout,
                    )
                    _print_status_and_headers(resp)
                    if getattr(ns, "fail", False) or getattr(ns, "fail_with_body", False):
                        if resp.status_code >= 400:
                            if getattr(ns, "fail_with_body", False):
                                body = resp.content
                                out_path = getattr(ns, "out", None)
                                if out_path:
                                    pp = Path(str(out_path))
                                    pp.parent.mkdir(parents=True, exist_ok=True)
                                    pp.write_bytes(body)
                                else:
                                    sys.stdout.write(body.decode("utf-8", errors="replace"))
                            sys.stderr.write(f"http error: {resp.status_code}\n")
                            return 1
                    _check_status(resp)
                    data = resp.json()

                    if ns.expect == "dict" and not isinstance(data, dict):
                        raise ValueError("expected dict")
                    if ns.expect == "list" and not isinstance(data, list):
                        raise ValueError("expected list")
                    if ns.expect == "any" and not isinstance(data, (dict, list)):
                        raise ValueError("expected dict or list")

                else:
                    try:
                        if ns.expect == "dict":
                            data = c.get_json_dict(
                                ns.url,
                                headers=_req_headers or None,
                                request_id=ns.request_id,
                                timeout=ns.timeout,
                            )
                        elif ns.expect == "list":
                            data = c.get_json_list(
                                ns.url,
                                headers=_req_headers or None,
                                request_id=ns.request_id,
                                timeout=ns.timeout,
                            )
                        else:
                            data = c.get_json_any(
                                ns.url,
                                headers=_req_headers or None,
                                request_id=ns.request_id,
                                timeout=ns.timeout,
                            )

                    except HttpStatusError as e:
                        if getattr(ns, "debug", False):
                            traceback.print_exc()
                        if getattr(ns, "verbose", False) and not _printed_req["v"]:
                            _verbose_request(
                                getattr(ns, "method", "GET"),
                                getattr(ns, "url", ""),
                                _merged_headers(
                                    raw, locals().get("headers"), getattr(ns, "debug", False)
                                ),
                            )
                        if (
                            getattr(ns, "fail", False) or getattr(ns, "fail_with_body", False)
                        ) and e.status_code >= 400:
                            if getattr(ns, "fail_with_body", False):
                                body = e.body
                                out_path = getattr(ns, "out", None)
                                if out_path:
                                    pp = Path(str(out_path))
                                    pp.parent.mkdir(parents=True, exist_ok=True)
                                    pp.write_bytes(body)
                                else:
                                    sys.stdout.write(body.decode("utf-8", errors="replace"))
                            sys.stderr.write(f"http error: {e.status_code}\n")
                            return 1
                        raise
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
        if getattr(ns, "verbose", False):
            _raw = locals().get("raw")
            _hdr_src = locals().get("headers") or {}
            try:
                _hdrs = (
                    _merged_headers(_raw, _hdr_src, getattr(ns, "debug", False))
                    if _raw is not None
                    else _hdr_src
                )
            except Exception:
                _hdrs = _hdr_src
            _verbose_request(getattr(ns, "method", "GET"), getattr(ns, "url", ""), _hdrs)
        if getattr(ns, "debug", False):
            traceback.print_exc()
        sys.stderr.write("request timed out\n")
        return 1
    except CircuitOpenError:
        if getattr(ns, "verbose", False):
            _raw = locals().get("raw")
            _hdr_src = locals().get("headers") or {}
            try:
                _hdrs = (
                    _merged_headers(_raw, _hdr_src, getattr(ns, "debug", False))
                    if _raw is not None
                    else _hdr_src
                )
            except Exception:
                _hdrs = _hdr_src
            _verbose_request(getattr(ns, "method", "GET"), getattr(ns, "url", ""), _hdrs)
        if getattr(ns, "debug", False):
            traceback.print_exc()
        sys.stderr.write("circuit open\n")
        return 1
    except ValueError as e:
        if getattr(ns, "verbose", False):
            _raw = locals().get("raw")
            _hdr_src = locals().get("headers") or {}
            try:
                _hdrs = (
                    _merged_headers(_raw, _hdr_src, getattr(ns, "debug", False))
                    if _raw is not None
                    else _hdr_src
                )
            except Exception:
                _hdrs = _hdr_src
            _verbose_request(getattr(ns, "method", "GET"), getattr(ns, "url", ""), _hdrs)
        if getattr(ns, "debug", False):
            traceback.print_exc()
        sys.stderr.write(str(e).rstrip() + "\n")
        return 1
    except (RuntimeError, AssertionError) as e:
        if getattr(ns, "verbose", False):
            _raw = locals().get("raw")
            _hdr_src = locals().get("headers") or {}
            try:
                _hdrs = (
                    _merged_headers(_raw, _hdr_src, getattr(ns, "debug", False))
                    if _raw is not None
                    else _hdr_src
                )
            except Exception:
                _hdrs = _hdr_src
            _verbose_request(getattr(ns, "method", "GET"), getattr(ns, "url", ""), _hdrs)
        if getattr(ns, "debug", False):
            traceback.print_exc()
        sys.stderr.write(str(e).rstrip() + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
