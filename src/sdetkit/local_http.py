"""Who may talk to SDETKit's local HTTP servers (`sdetkit serve` and `sdetkit ops serve`).

Both servers run repository checks and write files on request. They listened on
127.0.0.1 with no authentication, which only looks private: any web page the user had
open could send them a cross-site POST (a browser sends a "simple" request without asking
the server first), and a DNS-rebinding page could read the answers too. So:

- every request except the health check needs the server's bearer token, either generated
  at start-up or taken from ``SDETKIT_SERVER_TOKEN``;
- a server bound to a loopback address only answers requests addressed to a loopback name,
  which turns DNS-rebinding requests away;
- binding to any other interface needs an explicit ``--allow-remote``, because the servers
  speak plain HTTP.
"""

from __future__ import annotations

import hmac
import ipaddress
import os
import secrets
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN_ENV = "SDETKIT_SERVER_TOKEN"
_LOOPBACK_NAMES = frozenset({"localhost", "localhost."})


def is_loopback(host: str) -> bool:
    name = host.strip().strip("[]").lower()
    if name in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def check_bind(host: str, *, allow_remote: bool) -> None:
    """Refuse a non-loopback bind address unless the caller opted in."""

    if not is_loopback(host) and not allow_remote:
        raise ValueError(
            f"refusing to listen on {host}: the server speaks plain HTTP and runs checks on "
            "request; pass --allow-remote to listen on a non-loopback address"
        )


def server_token(explicit: str | None = None, environ: Mapping[str, str] | None = None) -> str:
    """The bearer token: the one given, else ``SDETKIT_SERVER_TOKEN``, else a fresh one."""

    env = os.environ if environ is None else environ
    return explicit or env.get(TOKEN_ENV, "").strip() or secrets.token_urlsafe(32)


def _host_name(header: str) -> str:
    header = header.strip()
    if header.startswith("["):
        return header[1:].split("]", 1)[0]
    return header.rsplit(":", 1)[0] if header.count(":") == 1 else header


def request_problem(
    headers: Mapping[str, str], *, token: str, bound_host: str
) -> tuple[HTTPStatus, str] | None:
    """Why a request must be refused, or None when it may proceed."""

    if is_loopback(bound_host) and not is_loopback(_host_name(headers.get("Host") or "")):
        return HTTPStatus.FORBIDDEN, "requests must be addressed to the loopback interface"
    supplied = headers.get("Authorization") or ""
    if not hmac.compare_digest(supplied.encode("utf-8"), f"Bearer {token}".encode()):
        return HTTPStatus.UNAUTHORIZED, (
            "missing or wrong bearer token: send 'Authorization: Bearer <token>' with the "
            f"token the server printed at start-up (or set {TOKEN_ENV} before starting it)"
        )
    return None


def startup_message(name: str, host: str, port: int, token: str, *, from_env: bool) -> str:
    where = f"{name} listening on http://{host}:{port}"
    if from_env:
        return f"{where}\nbearer token: taken from {TOKEN_ENV}"
    return f"{where}\nbearer token: {token}\n(set {TOKEN_ENV} to choose it)"


class GuardedHTTPServer(ThreadingHTTPServer):
    """A ThreadingHTTPServer that carries its bearer token and the host it was bound to."""

    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        *,
        token: str,
    ) -> None:
        super().__init__(address, handler)
        self.token = token
        self.bound_host = address[0]

    def refusal(self, handler: BaseHTTPRequestHandler) -> tuple[HTTPStatus, str] | None:
        headers = {key: handler.headers.get(key) or "" for key in ("Host", "Authorization")}
        return request_problem(headers, token=self.token, bound_host=self.bound_host)
