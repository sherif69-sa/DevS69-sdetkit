from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

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
                r = client.get(path)
            else:
                r = client.get(path, headers=hdrs)
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
                r = await client.get(path)
            else:
                r = await client.get(path, headers=hdrs)
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
                r = client.get(path)
            else:
                r = client.get(path, headers=hdrs)
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
                r = await client.get(path)
            else:
                r = await client.get(path, headers=hdrs)
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
