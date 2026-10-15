"""`sdetkit serve` and `sdetkit ops serve` answer only callers that hold their token.

Before, any web page open in the user's browser could POST to either server on
127.0.0.1 (a cross-site "simple" request needs no permission), and `/run-action` let a
caller write `report.build` output to any path, for example over a shell profile.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path

import pytest

from sdetkit import local_http
from sdetkit.cli import serve
from sdetkit.ops import create_server
from sdetkit.ops import ops as ops_module

TOKEN = "s3cret-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@contextmanager
def _running(server: local_http.GuardedHTTPServer) -> Iterator[str]:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _call(
    url: str, *, data: dict[str, object] | None = None, headers: dict[str, str] | None = None
) -> tuple[int, dict[str, object]]:
    body = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=5) as resp:  # noqa: S310 - local server
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


@pytest.mark.parametrize(
    ("host", "loopback"),
    [
        ("127.0.0.1", True),
        ("127.0.0.2", True),
        ("::1", True),
        ("[::1]", True),
        ("localhost", True),
        ("0.0.0.0", False),
        ("192.168.1.5", False),
        ("evil.example", False),
        ("localhost.evil.example", False),
    ],
)
def test_loopback_hosts(host: str, loopback: bool) -> None:
    assert local_http.is_loopback(host) is loopback


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ({"Host": "127.0.0.1:8765", **AUTH}, None),
        ({"Host": "localhost", **AUTH}, None),
        ({"Host": "[::1]:8765", **AUTH}, None),
        ({"Host": "127.0.0.1:8765"}, HTTPStatus.UNAUTHORIZED),
        ({"Host": "127.0.0.1:8765", "Authorization": "Bearer wrong"}, HTTPStatus.UNAUTHORIZED),
        ({"Host": "127.0.0.1:8765", "Authorization": TOKEN}, HTTPStatus.UNAUTHORIZED),
        # A DNS-rebinding page reaches the loopback server under its own name.
        ({"Host": "rebind.evil.example:8765", **AUTH}, HTTPStatus.FORBIDDEN),
        ({**AUTH}, HTTPStatus.FORBIDDEN),
    ],
)
def test_request_problem(headers: dict[str, str], status: HTTPStatus | None) -> None:
    problem = local_http.request_problem(headers, token=TOKEN, bound_host="127.0.0.1")
    assert (problem[0] if problem else None) == status


def test_a_remote_bind_checks_the_token_but_not_the_host_name() -> None:
    headers = {"Host": "build-box.internal:8765", **AUTH}
    assert local_http.request_problem(headers, token=TOKEN, bound_host="0.0.0.0") is None


def test_tokens_come_from_the_caller_then_the_environment_then_chance() -> None:
    env = {local_http.TOKEN_ENV: " from-env "}
    assert local_http.server_token("given", env) == "given"
    assert local_http.server_token(None, env) == "from-env"
    first, second = local_http.server_token(None, {}), local_http.server_token(None, {})
    assert first != second and len(first) >= 32


@pytest.mark.parametrize("make", [serve.build_server, None])
def test_non_loopback_binds_need_allow_remote(make: object) -> None:
    with pytest.raises(ValueError, match="--allow-remote"):
        if make is None:
            create_server("0.0.0.0", 0, Path("."))
        else:
            serve.build_server(host="0.0.0.0", port=0)


def test_the_clis_refuse_a_remote_bind_without_allow_remote(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert serve.main(["--host", "0.0.0.0", "--port", "0"]) == 2
    assert ops_module.main(["serve", "--host", "0.0.0.0", "--port", "0"]) == 2
    assert capsys.readouterr().err.count("--allow-remote") == 2


def test_ops_server_needs_the_token(tmp_path: Path) -> None:
    with _running(create_server("127.0.0.1", 0, tmp_path, token=TOKEN)) as base:
        assert _call(f"{base}/health")[0] == 200
        assert _call(f"{base}/actions")[0] == 401
        assert _call(f"{base}/actions", headers={"Authorization": "Bearer nope"})[0] == 401
        assert _call(f"{base}/actions", headers=AUTH)[0] == 200
        status, body = _call(f"{base}/actions", headers={**AUTH, "Host": "evil.example"})
        assert status == 403
        assert "loopback" in str(body["error"])


def test_a_cross_site_post_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "pwned.json"
    with _running(create_server("127.0.0.1", 0, tmp_path, token=TOKEN)) as base:
        request = {"action": "report.build", "inputs": {"output": str(target)}}
        # What a browser sends cross-site: text/plain, no credentials it does not hold.
        status, _ = _call(
            f"{base}/run-action", data=request, headers={"Content-Type": "text/plain"}
        )

    assert status == 401
    assert not target.exists()


@pytest.mark.parametrize("output", ["/tmp/sdetkit-escape.json", "../escape.json"])
def test_run_action_paths_stay_inside_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: str
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    with _running(create_server("127.0.0.1", 0, work, token=TOKEN)) as base:
        request = {"action": "report.build", "inputs": {"output": output}}
        status, body = _call(f"{base}/run-action", data=request, headers=AUTH)

    assert status == 400
    assert "output must stay inside" in str(body["error"])
    assert not (tmp_path / "escape.json").exists()


def test_run_action_still_writes_inside_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with _running(create_server("127.0.0.1", 0, tmp_path, token=TOKEN)) as base:
        request = {"action": "report.build", "inputs": {"output": "build/report.json"}}
        status, body = _call(f"{base}/run-action", data=request, headers=AUTH)

    assert status == 200
    assert Path(str(body["outputs"]["report_path"])) == tmp_path / "build" / "report.json"  # type: ignore[index]
    assert (tmp_path / "build" / "report.json").is_file()


def test_serve_needs_the_token_except_for_health() -> None:
    with _running(serve.build_server(host="127.0.0.1", port=0, token=TOKEN)) as base:
        assert _call(f"{base}/healthz")[0] == 200
        status, body = _call(f"{base}/v1/observability")
        assert status == 401
        assert body["error"]["code"] == "unauthorized"  # type: ignore[index]
        assert _call(f"{base}/v1/observability", headers=AUTH)[0] == 200
        assert _call(f"{base}/v1/review", data={"path": "."})[0] == 401


def test_startup_message_shows_a_generated_token_but_not_one_from_the_environment() -> None:
    shown = local_http.startup_message("sdetkit serve", "127.0.0.1", 8765, TOKEN, from_env=False)
    hidden = local_http.startup_message("sdetkit serve", "127.0.0.1", 8765, TOKEN, from_env=True)
    assert f"bearer token: {TOKEN}" in shown
    assert TOKEN not in hidden and local_http.TOKEN_ENV in hidden
