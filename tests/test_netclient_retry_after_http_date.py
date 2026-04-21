from __future__ import annotations

from sdetkit import netclient


def test_retry_after_seconds_supports_http_date_values() -> None:
    assert netclient._retry_after_seconds({"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"}) > 0.0
    assert netclient._retry_after_seconds({"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}) == 0.0
