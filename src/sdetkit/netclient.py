from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urljoin

import httpx

EventType = Literal[
    "attempt_start",
    "attempt_error",
    "attempt_response",
    "sleep",
    "complete",
]


@dataclass(frozen=True)
class ClientEvent:
    type: EventType
    url: str
    attempt: int
    retries: int
    request_id: str | None = None
    status_code: int | None = None
    error: str | None = None
    sleep_seconds: float | None = None
    elapsed_seconds: float | None = None
    ok: bool | None = None


Hook = Callable[[ClientEvent], None]
AsyncHook = Callable[[ClientEvent], Awaitable[None]]


@dataclass(frozen=True)
class RetryPolicy:
    retries: int = 1
    retry_on_429: bool = False
    backoff_base: float = 0.0
    backoff_factor: float = 2.0
    backoff_jitter: float = 0.0


class CircuitOpenError(RuntimeError):
    pass


class HttpStatusError(RuntimeError):
    def __init__(self, message: str, *, response: httpx.Response, body: bytes | None = None):
        super().__init__(message)
        self.response = response
        self.status_code = response.status_code
        try:
            self.url = str(response.request.url)
        except Exception:
            self.url = str(response.url)
        self.body = response.content if body is None else body


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    reset_seconds: float = 30.0
    _failures: int = 0
    _opened_at: float | None = None
    _half_open_used: bool = False

    def allow(self, now: float) -> None:
        if self._opened_at is None:
            return

        dt = now - self._opened_at
        if dt < self.reset_seconds:
            raise CircuitOpenError("circuit open")

        if self._half_open_used:
            raise CircuitOpenError("circuit open")

        self._half_open_used = True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._half_open_used = False

    def record_failure(self, now: float) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = now
            self._half_open_used = False


def _backoff_delay(attempt: int, base: float, factor: float, jitter: float) -> float:
    if base <= 0:
        return 0.0
    d = base * (factor**attempt)
    if jitter > 0:
        d += random.random() * jitter * d
    return d


def _retry_after_seconds(headers: Any) -> float | None:
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


def _merge_headers(
    headers: dict[str, str] | None,
    trace_header: str | None,
    request_id: str | None,
) -> tuple[dict[str, str] | None, str | None]:
    if trace_header is None:
        return (headers.copy() if headers else None), request_id
    rid = request_id or uuid.uuid4().hex
    out: dict[str, str] = {}
    if headers:
        out.update(headers)
    out[trace_header] = rid
    return out, rid


def _emit(hook: Hook | None, ev: ClientEvent) -> None:
    if hook is not None:
        hook(ev)


async def _emit_async(hook: Hook | AsyncHook | None, ev: ClientEvent) -> None:
    if hook is None:
        return
    r = hook(ev)
    if asyncio.iscoroutine(r):
        await r


class SdetHttpClient:
    def __init__(
        self,
        client: httpx.Client,
        *,
        retry: RetryPolicy | None = None,
        trace_header: str | None = None,
        breaker: CircuitBreaker | None = None,
        hook: Hook | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._client = client
        self._retry = retry or RetryPolicy()
        self._trace_header = trace_header
        self._breaker = breaker
        self._hook = hook
        self._clock = clock
        self._sleep = sleep

    def get_json_dict(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        request_id: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        retry: RetryPolicy | None = None,
        hook: Hook | None = None,
        breaker: CircuitBreaker | None = None,
    ) -> dict:
        r, data, rid = self._request_json(
            url,
            headers=headers,
            request_id=request_id,
            timeout=timeout,
            retry=retry,
            hook=hook,
            breaker=breaker,
        )
        if not isinstance(data, dict):
            raise ValueError("expected json object")
        return data

    def get_json_list(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        request_id: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        retry: RetryPolicy | None = None,
        hook: Hook | None = None,
        breaker: CircuitBreaker | None = None,
    ) -> list:
        r, data, rid = self._request_json(
            url,
            headers=headers,
            request_id=request_id,
            timeout=timeout,
            retry=retry,
            hook=hook,
            breaker=breaker,
        )
        if not isinstance(data, list):
            raise ValueError("expected json array")
        return data

    def get_json_list_paginated(
        self,
        url: str,
        *,
        max_pages: int = 100,
        headers: dict[str, str] | None = None,
        request_id: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        retry: RetryPolicy | None = None,
        hook: Hook | None = None,
        breaker: CircuitBreaker | None = None,
    ) -> list:
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")

        out: list = []
        seen: set[str] = set()
        cur = url

        for _ in range(max_pages):
            r, data, rid = self._request_json(
                cur,
                headers=headers,
                request_id=request_id,
                timeout=timeout,
                retry=retry,
                hook=hook,
                breaker=breaker,
            )
            if not isinstance(data, list):
                raise ValueError("expected json array")
            out.extend(data)

            nxt = _link_next_url(r)
            if not nxt:
                return out
            if nxt in seen:
                raise RuntimeError("pagination cycle")
            seen.add(nxt)
            cur = nxt

        raise RuntimeError("pagination limit exceeded")

    def _request_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None,
        request_id: str | None,
        timeout: float | httpx.Timeout | None,
        retry: RetryPolicy | None,
        hook: Hook | None,
        breaker: CircuitBreaker | None,
    ) -> tuple[httpx.Response, Any, str | None]:
        pol = retry or self._retry
        if pol.retries < 1:
            raise ValueError("retries must be >= 1")

        hdrs, rid = _merge_headers(headers, self._trace_header, request_id)
        h = hook or self._hook
        b = breaker or self._breaker
        start = self._clock()
        last_err: BaseException | None = None

        for attempt in range(pol.retries):
            if b is not None:
                b.allow(self._clock())

            _emit(
                h,
                ClientEvent(
                    type="attempt_start",
                    url=url,
                    attempt=attempt,
                    retries=pol.retries,
                    request_id=rid,
                ),
            )

            try:
                if hdrs is None:
                    r = self._client.get(url, timeout=timeout)
                else:
                    r = self._client.get(url, headers=hdrs, timeout=timeout)
            except httpx.TimeoutException as e:
                if b is not None:
                    b.record_failure(self._clock())
                _emit(
                    h,
                    ClientEvent(
                        type="attempt_error",
                        url=url,
                        attempt=attempt,
                        retries=pol.retries,
                        request_id=rid,
                        error="timeout",
                    ),
                )
                raise TimeoutError("request timed out") from e
            except httpx.RequestError as e:
                last_err = e
                if b is not None:
                    b.record_failure(self._clock())
                _emit(
                    h,
                    ClientEvent(
                        type="attempt_error",
                        url=url,
                        attempt=attempt,
                        retries=pol.retries,
                        request_id=rid,
                        error="request_error",
                    ),
                )

                if attempt < pol.retries - 1:
                    d = _backoff_delay(
                        attempt, pol.backoff_base, pol.backoff_factor, pol.backoff_jitter
                    )
                    if d > 0:
                        _emit(
                            h,
                            ClientEvent(
                                type="sleep",
                                url=url,
                                attempt=attempt,
                                retries=pol.retries,
                                request_id=rid,
                                sleep_seconds=d,
                            ),
                        )
                        self._sleep(d)
                    continue
                break

            _emit(
                h,
                ClientEvent(
                    type="attempt_response",
                    url=url,
                    attempt=attempt,
                    retries=pol.retries,
                    request_id=rid,
                    status_code=r.status_code,
                ),
            )

            if r.status_code == 429 and pol.retry_on_429 and attempt < pol.retries - 1:
                if b is not None:
                    b.record_failure(self._clock())
                ra = _retry_after_seconds(r.headers)
                d = (
                    ra
                    if ra is not None
                    else _backoff_delay(
                        attempt, pol.backoff_base, pol.backoff_factor, pol.backoff_jitter
                    )
                )
                if d > 0:
                    _emit(
                        h,
                        ClientEvent(
                            type="sleep",
                            url=url,
                            attempt=attempt,
                            retries=pol.retries,
                            request_id=rid,
                            sleep_seconds=d,
                        ),
                    )
                    self._sleep(d)
                continue

            if r.status_code < 200 or r.status_code >= 300:
                if b is not None:
                    b.record_failure(self._clock())
                elapsed = self._clock() - start
                _emit(
                    h,
                    ClientEvent(
                        type="complete",
                        url=url,
                        attempt=attempt,
                        retries=pol.retries,
                        request_id=rid,
                        ok=False,
                        elapsed_seconds=elapsed,
                    ),
                )
                raise HttpStatusError("non-2xx response", response=r, body=r.content)

            data = r.json()
            if b is not None:
                b.record_success()
            elapsed = self._clock() - start
            _emit(
                h,
                ClientEvent(
                    type="complete",
                    url=url,
                    attempt=attempt,
                    retries=pol.retries,
                    request_id=rid,
                    ok=True,
                    elapsed_seconds=elapsed,
                ),
            )
            return r, data, rid

        elapsed = self._clock() - start
        _emit(
            h,
            ClientEvent(
                type="complete",
                url=url,
                attempt=pol.retries - 1,
                retries=pol.retries,
                request_id=rid,
                ok=False,
                elapsed_seconds=elapsed,
            ),
        )
        if last_err is not None:
            raise RuntimeError("request failed") from last_err
        raise RuntimeError("request failed")


class SdetAsyncHttpClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        retry: RetryPolicy | None = None,
        trace_header: str | None = None,
        breaker: CircuitBreaker | None = None,
        hook: Hook | AsyncHook | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._client = client
        self._retry = retry or RetryPolicy()
        self._trace_header = trace_header
        self._breaker = breaker
        self._hook = hook
        self._clock = clock
        self._sleep = sleep

    async def get_json_dict(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        request_id: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        retry: RetryPolicy | None = None,
        hook: Hook | AsyncHook | None = None,
        breaker: CircuitBreaker | None = None,
    ) -> dict:
        r, data, rid = await self._request_json(
            url,
            headers=headers,
            request_id=request_id,
            timeout=timeout,
            retry=retry,
            hook=hook,
            breaker=breaker,
        )
        if not isinstance(data, dict):
            raise ValueError("expected json object")
        return data

    async def get_json_list(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        request_id: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        retry: RetryPolicy | None = None,
        hook: Hook | AsyncHook | None = None,
        breaker: CircuitBreaker | None = None,
    ) -> list:
        r, data, rid = await self._request_json(
            url,
            headers=headers,
            request_id=request_id,
            timeout=timeout,
            retry=retry,
            hook=hook,
            breaker=breaker,
        )
        if not isinstance(data, list):
            raise ValueError("expected json array")
        return data

    async def get_json_list_paginated(
        self,
        url: str,
        *,
        max_pages: int = 100,
        headers: dict[str, str] | None = None,
        request_id: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        retry: RetryPolicy | None = None,
        hook: Hook | AsyncHook | None = None,
        breaker: CircuitBreaker | None = None,
    ) -> list:
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")

        out: list = []
        seen: set[str] = set()
        cur = url

        for _ in range(max_pages):
            r, data, rid = await self._request_json(
                cur,
                headers=headers,
                request_id=request_id,
                timeout=timeout,
                retry=retry,
                hook=hook,
                breaker=breaker,
            )
            if not isinstance(data, list):
                raise ValueError("expected json array")
            out.extend(data)

            nxt = _link_next_url(r)
            if not nxt:
                return out
            if nxt in seen:
                raise RuntimeError("pagination cycle")
            seen.add(nxt)
            cur = nxt

        raise RuntimeError("pagination limit exceeded")

    async def _request_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None,
        request_id: str | None,
        timeout: float | httpx.Timeout | None,
        retry: RetryPolicy | None,
        hook: Hook | AsyncHook | None,
        breaker: CircuitBreaker | None,
    ) -> tuple[httpx.Response, Any, str | None]:
        pol = retry or self._retry
        if pol.retries < 1:
            raise ValueError("retries must be >= 1")

        hdrs, rid = _merge_headers(headers, self._trace_header, request_id)
        h = hook or self._hook
        b = breaker or self._breaker
        start = self._clock()
        last_err: BaseException | None = None

        for attempt in range(pol.retries):
            if b is not None:
                b.allow(self._clock())

            await _emit_async(
                h,
                ClientEvent(
                    type="attempt_start",
                    url=url,
                    attempt=attempt,
                    retries=pol.retries,
                    request_id=rid,
                ),
            )

            try:
                if hdrs is None:
                    r = await self._client.get(url, timeout=timeout)
                else:
                    r = await self._client.get(url, headers=hdrs, timeout=timeout)
            except httpx.TimeoutException as e:
                if b is not None:
                    b.record_failure(self._clock())
                await _emit_async(
                    h,
                    ClientEvent(
                        type="attempt_error",
                        url=url,
                        attempt=attempt,
                        retries=pol.retries,
                        request_id=rid,
                        error="timeout",
                    ),
                )
                raise TimeoutError("request timed out") from e
            except httpx.RequestError as e:
                last_err = e
                if b is not None:
                    b.record_failure(self._clock())
                await _emit_async(
                    h,
                    ClientEvent(
                        type="attempt_error",
                        url=url,
                        attempt=attempt,
                        retries=pol.retries,
                        request_id=rid,
                        error="request_error",
                    ),
                )

                if attempt < pol.retries - 1:
                    d = _backoff_delay(
                        attempt, pol.backoff_base, pol.backoff_factor, pol.backoff_jitter
                    )
                    if d > 0:
                        await _emit_async(
                            h,
                            ClientEvent(
                                type="sleep",
                                url=url,
                                attempt=attempt,
                                retries=pol.retries,
                                request_id=rid,
                                sleep_seconds=d,
                            ),
                        )
                        await self._sleep(d)
                    continue
                break

            await _emit_async(
                h,
                ClientEvent(
                    type="attempt_response",
                    url=url,
                    attempt=attempt,
                    retries=pol.retries,
                    request_id=rid,
                    status_code=r.status_code,
                ),
            )

            if r.status_code == 429 and pol.retry_on_429 and attempt < pol.retries - 1:
                if b is not None:
                    b.record_failure(self._clock())
                ra = _retry_after_seconds(r.headers)
                d = (
                    ra
                    if ra is not None
                    else _backoff_delay(
                        attempt, pol.backoff_base, pol.backoff_factor, pol.backoff_jitter
                    )
                )
                if d > 0:
                    await _emit_async(
                        h,
                        ClientEvent(
                            type="sleep",
                            url=url,
                            attempt=attempt,
                            retries=pol.retries,
                            request_id=rid,
                            sleep_seconds=d,
                        ),
                    )
                    await self._sleep(d)
                continue

            if r.status_code < 200 or r.status_code >= 300:
                if b is not None:
                    b.record_failure(self._clock())
                elapsed = self._clock() - start
                await _emit_async(
                    h,
                    ClientEvent(
                        type="complete",
                        url=url,
                        attempt=attempt,
                        retries=pol.retries,
                        request_id=rid,
                        ok=False,
                        elapsed_seconds=elapsed,
                    ),
                )
                raise HttpStatusError("non-2xx response", response=r, body=r.content)

            data = r.json()
            if b is not None:
                b.record_success()
            elapsed = self._clock() - start
            await _emit_async(
                h,
                ClientEvent(
                    type="complete",
                    url=url,
                    attempt=attempt,
                    retries=pol.retries,
                    request_id=rid,
                    ok=True,
                    elapsed_seconds=elapsed,
                ),
            )
            return r, data, rid

        elapsed = self._clock() - start
        await _emit_async(
            h,
            ClientEvent(
                type="complete",
                url=url,
                attempt=pol.retries - 1,
                retries=pol.retries,
                request_id=rid,
                ok=False,
                elapsed_seconds=elapsed,
            ),
        )
        if last_err is not None:
            raise RuntimeError("request failed") from last_err
        raise RuntimeError("request failed")
