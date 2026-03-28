from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .security import safe_path


def _b64e(b: bytes) -> str:
    if not b:
        return ""
    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    if not s:
        return b""
    return base64.b64decode(s.encode("ascii"))


def _headers_to_list(h: httpx.Headers) -> list[list[str]]:
    return [[k, v] for k, v in h.multi_items()]


def _headers_from_list(items: list[list[str]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for kv in items:
        if not (isinstance(kv, list) and len(kv) == 2):
            continue
        k, v = kv
        if isinstance(k, str) and isinstance(v, str):
            out.append((k, v))
    return out


@dataclass(frozen=True)
class _Key:
    method: str
    url: str
    body_b64: str


class Cassette:
    def __init__(self, interactions: list[dict[str, Any]] | None = None) -> None:
        self.interactions: list[dict[str, Any]] = interactions or []

    def to_json(self) -> dict[str, Any]:
        return {"version": 1, "interactions": self.interactions}

    def save(self, path: str | Path, *, allow_absolute: bool = False) -> None:
        p = safe_path(Path.cwd(), str(path), allow_absolute=allow_absolute)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_json(), ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path, *, allow_absolute: bool = False) -> Cassette:
        p = safe_path(Path.cwd(), str(path), allow_absolute=allow_absolute)
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("invalid cassette: expected object")
        inter = data.get("interactions")
        if not isinstance(inter, list):
            raise ValueError("invalid cassette: expected interactions list")
        out: list[dict[str, Any]] = []
        for it in inter:
            if isinstance(it, dict):
                out.append(it)
        return cls(out)

    def _key_for_request(self, req: httpx.Request) -> _Key:
        body = req.content if isinstance(req.content, bytes | bytearray) else b""
        return _Key(req.method.upper(), str(req.url), _b64e(bytes(body)))

    def append(self, req: httpx.Request, resp: httpx.Response, body: bytes) -> None:
        self.interactions.append(
            {
                "request": {
                    "method": req.method.upper(),
                    "url": str(req.url),
                    "headers": _headers_to_list(req.headers),
                    "body_b64": _b64e(
                        req.content if isinstance(req.content, bytes | bytearray) else b""
                    ),
                },
                "response": {
                    "status_code": int(resp.status_code),
                    "headers": _headers_to_list(resp.headers),
                    "body_b64": _b64e(body),
                },
            }
        )


class CassetteReplayTransport(httpx.BaseTransport):
    def __init__(self, cassette: Cassette) -> None:
        self._cassette = cassette
        self._i = 0

    def assert_exhausted(self) -> None:
        if self._i != len(self._cassette.interactions):
            raise AssertionError(
                f"cassette not exhausted: played={self._i} total={len(self._cassette.interactions)}"
            )

    def close(self) -> None:
        self.assert_exhausted()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._i >= len(self._cassette.interactions):
            raise RuntimeError("cassette mismatch: no more recorded interactions")

        it = self._cassette.interactions[self._i]
        self._i += 1

        rreq = it.get("request")
        rresp = it.get("response")
        if not isinstance(rreq, dict) or not isinstance(rresp, dict):
            raise RuntimeError("cassette mismatch: invalid interaction shape")

        method = rreq.get("method")
        url = rreq.get("url")
        body_b64 = rreq.get("body_b64", "")
        key_expected = _Key(
            str(method).upper() if isinstance(method, str) else "",
            str(url) if isinstance(url, str) else "",
            str(body_b64) if isinstance(body_b64, str) else "",
        )
        key_got = self._cassette._key_for_request(request)

        if key_expected != key_got:
            raise RuntimeError(
                f"cassette mismatch: expected {key_expected.method} {key_expected.url} got {key_got.method} {key_got.url}"
            )

        status = rresp.get("status_code")
        hdrs = rresp.get("headers")
        body = rresp.get("body_b64", "")
        if not isinstance(status, int) or not isinstance(hdrs, list) or not isinstance(body, str):
            raise RuntimeError("cassette mismatch: invalid response shape")

        return httpx.Response(
            status_code=status,
            headers=_headers_from_list(hdrs),
            content=_b64d(body),
            request=request,
        )


class CassetteRecordTransport(httpx.BaseTransport):
    def __init__(
        self,
        cassette: Cassette,
        inner: httpx.BaseTransport,
        *,
        path: str | Path | None = None,
        allow_absolute: bool = False,
    ) -> None:
        self._cassette = cassette
        self._inner = inner
        self._path = str(path) if path is not None else None
        self._allow_absolute = allow_absolute

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        resp = self._inner.handle_request(request)
        body = resp.read()
        self._cassette.append(request, resp, body)
        return resp

    def close(self) -> None:
        try:
            if self._path is not None and self._cassette.interactions:
                self._cassette.save(self._path, allow_absolute=self._allow_absolute)
        finally:
            self._inner.close()


class AsyncCassetteReplayTransport(httpx.AsyncBaseTransport):
    def __init__(self, cassette: Cassette) -> None:
        self._cassette = cassette
        self._i = 0

    def assert_exhausted(self) -> None:
        if self._i != len(self._cassette.interactions):
            raise AssertionError(
                f"cassette not exhausted: played={self._i} total={len(self._cassette.interactions)}"
            )

    async def aclose(self) -> None:
        self.assert_exhausted()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self._i >= len(self._cassette.interactions):
            raise RuntimeError("cassette mismatch: no more recorded interactions")

        it = self._cassette.interactions[self._i]
        self._i += 1

        rreq = it.get("request")
        rresp = it.get("response")
        if not isinstance(rreq, dict) or not isinstance(rresp, dict):
            raise RuntimeError("cassette mismatch: invalid interaction shape")

        method = rreq.get("method")
        url = rreq.get("url")
        body_b64 = rreq.get("body_b64", "")
        key_expected = _Key(
            str(method).upper() if isinstance(method, str) else "",
            str(url) if isinstance(url, str) else "",
            str(body_b64) if isinstance(body_b64, str) else "",
        )
        key_got = self._cassette._key_for_request(request)

        if key_expected != key_got:
            raise RuntimeError(
                f"cassette mismatch: expected {key_expected.method} {key_expected.url} got {key_got.method} {key_got.url}"
            )

        status = rresp.get("status_code")
        hdrs = rresp.get("headers")
        body = rresp.get("body_b64", "")
        if not isinstance(status, int) or not isinstance(hdrs, list) or not isinstance(body, str):
            raise RuntimeError("cassette mismatch: invalid response shape")

        return httpx.Response(
            status_code=status,
            headers=_headers_from_list(hdrs),
            content=_b64d(body),
            request=request,
        )


class AsyncCassetteRecordTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        cassette: Cassette,
        inner: httpx.AsyncBaseTransport,
        *,
        path: str | Path | None = None,
        allow_absolute: bool = False,
    ) -> None:
        self._cassette = cassette
        self._inner = inner
        self._path = str(path) if path is not None else None
        self._allow_absolute = allow_absolute

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        resp = await self._inner.handle_async_request(request)
        body = await resp.aread()
        self._cassette.append(request, resp, body)
        return resp

    async def aclose(self) -> None:
        try:
            if self._path is not None and self._cassette.interactions:
                self._cassette.save(self._path, allow_absolute=self._allow_absolute)
        finally:
            await self._inner.aclose()


def open_transport(
    path: str | Path,
    mode: str = "auto",
    *,
    upstream: httpx.BaseTransport | None = None,
    allow_absolute: bool = False,
) -> httpx.BaseTransport:
    p = safe_path(Path.cwd(), str(path), allow_absolute=allow_absolute)
    m = mode.lower().strip()

    if m == "auto":
        m = "replay" if p.exists() else "record"
    if m not in {"record", "replay"}:
        raise ValueError("cassette mode must be one of: auto, record, replay")

    if m == "replay":
        if not p.exists():
            raise RuntimeError("cassette not found")
        cassette = Cassette.load(p, allow_absolute=True)
        return CassetteReplayTransport(cassette)

    cassette = Cassette([])
    inner = upstream if upstream is not None else httpx.HTTPTransport()
    return CassetteRecordTransport(cassette, inner, path=p, allow_absolute=True)
