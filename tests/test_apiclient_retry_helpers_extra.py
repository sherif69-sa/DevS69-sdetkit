from __future__ import annotations

import math

from sdetkit import apiclient


class _BadHeaders:
    def get(self, name: str):
        raise RuntimeError("boom")


def test_retry_after_seconds_defensive_paths() -> None:
    assert apiclient._retry_after_seconds({"Retry-After": "12"}) == 12.0
    assert apiclient._retry_after_seconds({"Retry-After": "oops"}) is None
    assert apiclient._retry_after_seconds(_BadHeaders()) is None


def test_backoff_and_header_merge_edges(monkeypatch) -> None:
    monkeypatch.setattr(apiclient.random, "random", lambda: 0.5)
    delay = apiclient._backoff_delay(attempt=2, base=1.0, factor=2.0, jitter=0.1)
    assert math.isclose(delay, 4.2)
    assert apiclient._backoff_delay(attempt=1, base=0.0, factor=2.0, jitter=1.0) == 0.0

    assert apiclient._merge_headers(None, None, None) is None
    merged = apiclient._merge_headers({"A": "1"}, "X-Trace", "rid")
    assert merged == {"A": "1", "X-Trace": "rid"}
