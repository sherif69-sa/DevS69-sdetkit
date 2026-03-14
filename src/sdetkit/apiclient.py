from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urljoin

import httpx


def _backoff_delay(attempt: int, base: float, factor: float, jitter: float) -> float:
    if base <= 0:
        return 0.0
    d = base * (factor**attempt)
    if jitter > 0:
        d += random.random() * jitter * d
    return d


def _retry_after_seconds(headers: Any) -> float | None:
    v = None
    try:
        v = headers.get("Retry-After")
    except Exception:
        v = None
    if not v:
        return None
    try:
        return float(int(str(v).strip()))
    except Exception:
        return None


def _merge_headers(
    headers: dict[str, str] | None, trace_header: str | None, request_id: str | None
) -> dict[str, str] | None:
    if headers is None and trace_header is None:
        return None
    out: dict[str, str] = {}
    if headers:
        out.update(headers)
    if trace_header is not None:
        rid = request_id or uuid.uuid4().hex
        out[trace_header] = rid
    return out


def fetch_json_dict(
    client: httpx.Client,
    path: str,
    retries: int = 1,
    *,
    timeout: float | httpx.Timeout | None = None,
    headers: dict[str, str] | None = None,
    trace_header: str | None = None,
    request_id: str | None = None,
    retry_on_429: bool = False,
    backoff_base: float = 0.0,
    backoff_factor: float = 2.0,
    backoff_jitter: float = 0.0,
    sleep: Callable[[float], None] | None = None,
) -> dict:
    if retries < 1:
        raise ValueError("retries must be >= 1")

    hdrs = _merge_headers(headers, trace_header, request_id)
    sleep_fn = sleep or time.sleep

    last_err = None  # pragma: no mutate
    for attempt in range(retries):
        try:
            if hdrs is None:
                r = client.get(path, timeout=timeout)
            else:
                r = client.get(path, headers=hdrs, timeout=timeout)
            last_err = None  # pragma: no mutate
        except httpx.TimeoutException as e:
            raise TimeoutError("request timed out") from e
        except httpx.RequestError as e:
            last_err = e
            if attempt < retries - 1:
                d = _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
                if d > 0:
                    sleep_fn(d)
                continue
            r = None  # pragma: no mutate

        if last_err is not None:
            continue

        if r is None:
            continue

        if r.status_code == 429 and retry_on_429 and attempt < retries - 1:
            ra = _retry_after_seconds(r.headers)
            d = (
                ra
                if ra is not None
                else _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
            )
            if d > 0:
                sleep_fn(d)
            continue

        if r.status_code < 200 or r.status_code >= 300:
            raise RuntimeError("non-2xx response")

        data = r.json()
        if not isinstance(data, dict):
            raise ValueError("expected json object")
        return data

    if last_err is not None:
        raise RuntimeError("request failed") from last_err

    raise RuntimeError("request failed")


async def fetch_json_dict_async(
    client: httpx.AsyncClient,
    path: str,
    retries: int = 1,
    *,
    timeout: float | httpx.Timeout | None = None,
    headers: dict[str, str] | None = None,
    trace_header: str | None = None,
    request_id: str | None = None,
    retry_on_429: bool = False,
    backoff_base: float = 0.0,
    backoff_factor: float = 2.0,
    backoff_jitter: float = 0.0,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> dict:
    if retries < 1:
        raise ValueError("retries must be >= 1")

    hdrs = _merge_headers(headers, trace_header, request_id)
    sleep_fn = sleep or asyncio.sleep

    last_err = None  # pragma: no mutate
    for attempt in range(retries):
        try:
            if hdrs is None:
                r = await client.get(path, timeout=timeout)
            else:
                r = await client.get(path, headers=hdrs, timeout=timeout)
            last_err = None  # pragma: no mutate
        except httpx.TimeoutException as e:
            raise TimeoutError("request timed out") from e
        except httpx.RequestError as e:
            last_err = e
            if attempt < retries - 1:
                d = _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
                if d > 0:
                    await sleep_fn(d)
                continue
            r = None  # pragma: no mutate

        if last_err is not None:
            continue

        if r is None:
            continue

        if r.status_code == 429 and retry_on_429 and attempt < retries - 1:
            ra = _retry_after_seconds(r.headers)
            d = (
                ra
                if ra is not None
                else _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
            )
            if d > 0:
                await sleep_fn(d)
            continue

        if r.status_code < 200 or r.status_code >= 300:
            raise RuntimeError("non-2xx response")

        data = r.json()
        if not isinstance(data, dict):
            raise ValueError("expected json object")
        return data

    if last_err is not None:
        raise RuntimeError("request failed") from last_err

    raise RuntimeError("request failed")


def fetch_json_list(
    client: httpx.Client,
    path: str,
    retries: int = 1,
    *,
    timeout: float | httpx.Timeout | None = None,
    headers: dict[str, str] | None = None,
    trace_header: str | None = None,
    request_id: str | None = None,
    retry_on_429: bool = False,
    backoff_base: float = 0.0,
    backoff_factor: float = 2.0,
    backoff_jitter: float = 0.0,
    sleep: Callable[[float], None] | None = None,
) -> list:
    if retries < 1:
        raise ValueError("retries must be >= 1")

    hdrs = _merge_headers(headers, trace_header, request_id)
    sleep_fn = sleep or time.sleep

    last_err = None  # pragma: no mutate
    for attempt in range(retries):
        try:
            if hdrs is None:
                r = client.get(path, timeout=timeout)
            else:
                r = client.get(path, headers=hdrs, timeout=timeout)
            last_err = None  # pragma: no mutate
        except httpx.TimeoutException as e:
            raise TimeoutError("request timed out") from e
        except httpx.RequestError as e:
            last_err = e
            if attempt < retries - 1:
                d = _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
                if d > 0:
                    sleep_fn(d)
                continue
            r = None  # pragma: no mutate

        if last_err is not None:
            continue

        if r is None:
            continue

        if r.status_code == 429 and retry_on_429 and attempt < retries - 1:
            ra = _retry_after_seconds(r.headers)
            d = (
                ra
                if ra is not None
                else _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
            )
            if d > 0:
                sleep_fn(d)
            continue

        if r.status_code < 200 or r.status_code >= 300:
            raise RuntimeError("non-2xx response")

        data = r.json()
        if not isinstance(data, list):
            raise ValueError("expected json array")
        return data

    if last_err is not None:
        raise RuntimeError("request failed") from last_err

    raise RuntimeError("request failed")


async def fetch_json_list_async(
    client: httpx.AsyncClient,
    path: str,
    retries: int = 1,
    *,
    timeout: float | httpx.Timeout | None = None,
    headers: dict[str, str] | None = None,
    trace_header: str | None = None,
    request_id: str | None = None,
    retry_on_429: bool = False,
    backoff_base: float = 0.0,
    backoff_factor: float = 2.0,
    backoff_jitter: float = 0.0,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> list:
    if retries < 1:
        raise ValueError("retries must be >= 1")

    hdrs = _merge_headers(headers, trace_header, request_id)
    sleep_fn = sleep or asyncio.sleep

    last_err = None  # pragma: no mutate
    for attempt in range(retries):
        try:
            if hdrs is None:
                r = await client.get(path, timeout=timeout)
            else:
                r = await client.get(path, headers=hdrs, timeout=timeout)
            last_err = None  # pragma: no mutate
        except httpx.TimeoutException as e:
            raise TimeoutError("request timed out") from e
        except httpx.RequestError as e:
            last_err = e
            if attempt < retries - 1:
                d = _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
                if d > 0:
                    await sleep_fn(d)
                continue
            r = None  # pragma: no mutate

        if last_err is not None:
            continue

        if r is None:
            continue

        if r.status_code == 429 and retry_on_429 and attempt < retries - 1:
            ra = _retry_after_seconds(r.headers)
            d = (
                ra
                if ra is not None
                else _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
            )
            if d > 0:
                await sleep_fn(d)
            continue

        if r.status_code < 200 or r.status_code >= 300:
            raise RuntimeError("non-2xx response")

        data = r.json()
        if not isinstance(data, list):
            raise ValueError("expected json array")
        return data

    if last_err is not None:
        raise RuntimeError("request failed") from last_err

    raise RuntimeError("request failed")


def _link_next_url(r: httpx.Response) -> str | None:
    link = r.headers.get("Link")
    if not link:
        return None

    for part in (p.strip() for p in link.split(",")):
        if "rel=" not in part:
            continue
        segs = [s.strip() for s in part.split(";")]
        if not segs:
            continue

        u = segs[0]
        if not (u.startswith("<") and ">" in u):
            continue
        url = u[1 : u.find(">")].strip()

        rel = None
        for s in segs[1:]:
            if s.startswith("rel="):
                rel = s[4:].strip()
                if rel.startswith('"') and rel.endswith('"') and len(rel) >= 2:
                    rel = rel[1:-1]
                break

        if rel == "next":
            return str(urljoin(str(r.url), url))

    return None


def _fetch_json_list_response(
    client: httpx.Client,
    url: str,
    retries: int,
    *,
    headers: dict[str, str] | None,
    retry_on_429: bool,
    backoff_base: float,
    backoff_factor: float,
    backoff_jitter: float,
    timeout: float | httpx.Timeout | None,
    sleep: Callable[[float], None] | None,
) -> tuple[httpx.Response, list]:
    sleep_fn = sleep or time.sleep
    last_err = None  # pragma: no mutate

    for attempt in range(retries):
        try:
            if headers is None:
                r = client.get(url, timeout=timeout)
            else:
                r = client.get(url, headers=headers, timeout=timeout)
            last_err = None  # pragma: no mutate
        except httpx.TimeoutException as e:
            raise TimeoutError("request timed out") from e
        except httpx.RequestError as e:
            last_err = e
            if attempt < retries - 1:
                d = _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
                if d > 0:
                    sleep_fn(d)
                continue
            r = None  # pragma: no mutate

        if last_err is not None or r is None:
            continue

        if r.status_code == 429 and retry_on_429 and attempt < retries - 1:
            ra = _retry_after_seconds(r.headers)
            d = (
                ra
                if ra is not None
                else _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
            )
            if d > 0:
                sleep_fn(d)
            continue

        if r.status_code < 200 or r.status_code >= 300:
            raise RuntimeError("non-2xx response")

        data = r.json()
        if not isinstance(data, list):
            raise ValueError("expected json array")
        return r, data

    if last_err is not None:
        raise RuntimeError("request failed") from last_err

    raise RuntimeError("request failed")


async def _fetch_json_list_response_async(
    client: httpx.AsyncClient,
    url: str,
    retries: int,
    *,
    headers: dict[str, str] | None,
    retry_on_429: bool,
    backoff_base: float,
    backoff_factor: float,
    backoff_jitter: float,
    timeout: float | httpx.Timeout | None,
    sleep: Callable[[float], Awaitable[None]] | None,
) -> tuple[httpx.Response, list]:
    sleep_fn = sleep or asyncio.sleep
    last_err = None  # pragma: no mutate

    for attempt in range(retries):
        try:
            if headers is None:
                r = await client.get(url, timeout=timeout)
            else:
                r = await client.get(url, headers=headers, timeout=timeout)
            last_err = None  # pragma: no mutate
        except httpx.TimeoutException as e:
            raise TimeoutError("request timed out") from e
        except httpx.RequestError as e:
            last_err = e
            if attempt < retries - 1:
                d = _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
                if d > 0:
                    await sleep_fn(d)
                continue
            r = None  # pragma: no mutate

        if last_err is not None or r is None:
            continue

        if r.status_code == 429 and retry_on_429 and attempt < retries - 1:
            ra = _retry_after_seconds(r.headers)
            d = (
                ra
                if ra is not None
                else _backoff_delay(attempt, backoff_base, backoff_factor, backoff_jitter)
            )
            if d > 0:
                await sleep_fn(d)
            continue

        if r.status_code < 200 or r.status_code >= 300:
            raise RuntimeError("non-2xx response")

        data = r.json()
        if not isinstance(data, list):
            raise ValueError("expected json array")
        return r, data

    if last_err is not None:
        raise RuntimeError("request failed") from last_err

    raise RuntimeError("request failed")


def fetch_json_list_paginated(
    client: httpx.Client,
    path: str,
    retries: int = 1,
    *,
    max_pages: int = 100,
    headers: dict[str, str] | None = None,
    trace_header: str | None = None,
    request_id: str | None = None,
    retry_on_429: bool = False,
    backoff_base: float = 0.0,
    backoff_factor: float = 2.0,
    backoff_jitter: float = 0.0,
    timeout: float | httpx.Timeout | None = None,
    sleep: Callable[[float], None] | None = None,
) -> list:
    if retries < 1:
        raise ValueError("retries must be >= 1")
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")

    rid = request_id
    if trace_header is not None and rid is None:
        rid = uuid.uuid4().hex
    hdrs = _merge_headers(headers, trace_header, rid)

    out: list = []
    url = path
    seen: set[str] = set()

    for _ in range(max_pages):
        r, page = _fetch_json_list_response(
            client,
            url,
            retries,
            headers=hdrs,
            retry_on_429=retry_on_429,
            backoff_base=backoff_base,
            backoff_factor=backoff_factor,
            backoff_jitter=backoff_jitter,
            timeout=timeout,
            sleep=sleep,
        )
        out.extend(page)

        nxt = _link_next_url(r)
        if not nxt:
            return out

        if nxt in seen:
            raise RuntimeError("pagination impact")
        seen.add(nxt)
        url = nxt

    raise RuntimeError("pagination limit exceeded")


async def fetch_json_list_paginated_async(
    client: httpx.AsyncClient,
    path: str,
    retries: int = 1,
    *,
    max_pages: int = 100,
    headers: dict[str, str] | None = None,
    trace_header: str | None = None,
    request_id: str | None = None,
    retry_on_429: bool = False,
    backoff_base: float = 0.0,
    backoff_factor: float = 2.0,
    backoff_jitter: float = 0.0,
    timeout: float | httpx.Timeout | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> list:
    if retries < 1:
        raise ValueError("retries must be >= 1")
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")

    rid = request_id
    if trace_header is not None and rid is None:
        rid = uuid.uuid4().hex
    hdrs = _merge_headers(headers, trace_header, rid)

    out: list = []
    url = path
    seen: set[str] = set()

    for _ in range(max_pages):
        r, page = await _fetch_json_list_response_async(
            client,
            url,
            retries,
            headers=hdrs,
            retry_on_429=retry_on_429,
            backoff_base=backoff_base,
            backoff_factor=backoff_factor,
            backoff_jitter=backoff_jitter,
            timeout=timeout,
            sleep=sleep,
        )
        out.extend(page)

        nxt = _link_next_url(r)
        if not nxt:
            return out

        if nxt in seen:
            raise RuntimeError("pagination impact")
        seen.add(nxt)
        url = nxt

    raise RuntimeError("pagination limit exceeded")
