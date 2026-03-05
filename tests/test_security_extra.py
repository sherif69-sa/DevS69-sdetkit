from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import security


def test_redaction_helpers_cover_paths() -> None:
    keys = security.redact_keys(["X-Key"])
    assert security.is_sensitive_key("x-key", keys)
    assert (
        security.redact_header_value("authorization", "abc", enabled=True, keys=keys)
        == "<redacted>"
    )
    assert security.redact_header_value("x", "abc", enabled=False, keys=keys) == "abc"

    obj = {"token": "a", "nested": [{"password": "b"}, 1]}
    red = security.redact_json(obj, enabled=True, keys=keys)
    assert red["token"] == "<redacted>"
    assert red["nested"][0]["password"] == "<redacted>"

    txt = security.redact_secrets_text("token=abc password:xyz", enabled=True, keys=keys)
    assert "<redacted>" in txt

    jtxt = security.redact_json_text('{"token":"x"}', enabled=True, keys=keys)
    assert json.loads(jtxt)["token"] == "<redacted>"


def test_safe_path_and_scheme_validation(tmp_path: Path) -> None:
    root = tmp_path
    assert security.safe_path(root, "a/b.txt") == (root / "a" / "b.txt")
    abs_path = security.safe_path(root, "/tmp/x", allow_absolute=True)
    assert abs_path.as_posix().endswith("/tmp/x")

    with pytest.raises(security.SecurityError):
        security.safe_path(root, "../x")
    with pytest.raises(security.SecurityError):
        security.ensure_allowed_scheme("ftp://x", allowed={"http", "https"})

    timeout = security.default_http_timeout(None)
    assert timeout is not None
