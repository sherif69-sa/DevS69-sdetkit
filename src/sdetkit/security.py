from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

DEFAULT_REDACT_KEYS: frozenset[str] = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api_key",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "session",
    }
)


class SecurityError(ValueError):
    pass


def redact_keys(extra: list[str] | None = None) -> set[str]:
    out = set(DEFAULT_REDACT_KEYS)
    for k in extra or []:
        key = str(k).strip().lower()
        if key:
            out.add(key)
    return out


def is_sensitive_key(name: str, keys: set[str]) -> bool:
    key = str(name).strip().lower()
    if key in keys:
        return True
    key_norm = key.replace("-", "_")
    return key_norm in keys


def redact_header_value(name: str, value: str, *, enabled: bool, keys: set[str]) -> str:
    if enabled and is_sensitive_key(name, keys):
        return "<redacted>"
    return value


def redact_json(value: object, *, enabled: bool, keys: set[str]) -> object:
    if not enabled:
        return value
    if isinstance(value, dict):
        out: dict[object, object] = {}
        for k in sorted(value.keys(), key=str):
            v = value[k]
            if isinstance(k, str) and is_sensitive_key(k, keys):
                out[k] = "<redacted>"
            else:
                out[k] = redact_json(v, enabled=enabled, keys=keys)
        return out
    if isinstance(value, list):
        return [redact_json(v, enabled=enabled, keys=keys) for v in value]
    return value


def redact_secrets_text(text: str, *, enabled: bool, keys: set[str]) -> str:
    if not enabled:
        return text
    out = text
    for key in sorted(keys):
        token = re.escape(key).replace("\\-", "[-_]").replace("\\_", "[-_]")
        pattern = rf"(?i)(\b{token}\b\s*[:=]\s*)([^\s,;]+)"
        out = re.sub(pattern, r"\1<redacted>", out)
    return out


def redact_secrets_headers(
    headers: dict[str, str], *, enabled: bool, keys: set[str]
) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in sorted(headers):
        out[key] = redact_header_value(key, str(headers[key]), enabled=enabled, keys=keys)
    return out


def redact_secrets_json(value: object, *, enabled: bool, keys: set[str]) -> object:
    return redact_json(value, enabled=enabled, keys=keys)


def redact_json_text(text: str, *, enabled: bool, keys: set[str]) -> str:
    try:
        raw = json.loads(text)
    except ValueError:
        return text
    return json.dumps(redact_json(raw, enabled=enabled, keys=keys), sort_keys=True)


def redact_url(url: str, *, enabled: bool, keys: set[str]) -> str:
    if not enabled:
        return url
    split = urlsplit(url)
    q = []
    for k, v in parse_qsl(split.query, keep_blank_values=True):
        q.append((k, "<redacted>" if is_sensitive_key(k, keys) else v))
    return urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(q, doseq=True), split.fragment)
    )


def ensure_allowed_scheme(url: str, *, allowed: set[str]) -> None:
    scheme = urlsplit(url).scheme.lower()
    if scheme == "":
        return
    if scheme not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise SecurityError(f"URL scheme '{scheme}' is not allowed (allowed: {allowed_list})")


def safe_path(root: Path, user_path: str, *, allow_absolute: bool = False) -> Path:
    if "\x00" in user_path:
        raise SecurityError("unsafe path rejected: contains NUL byte")
    p = Path(user_path)
    if p.is_absolute() and not allow_absolute:
        raise SecurityError("unsafe path rejected: absolute paths require explicit allow")
    if any(part == ".." for part in p.parts):
        raise SecurityError("unsafe path rejected: traversal is not allowed")

    base = p if p.is_absolute() else (root / p)
    resolved_target = base.resolve(strict=False)
    if not p.is_absolute() or not allow_absolute:
        resolved_root = root.resolve(strict=True)
        if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
            raise SecurityError("unsafe path rejected: escapes root")
    return resolved_target


def default_http_timeout(timeout_seconds: float | None = None) -> httpx.Timeout:
    if timeout_seconds is not None:
        return httpx.Timeout(timeout_seconds)
    return httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
