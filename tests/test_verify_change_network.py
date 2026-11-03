"""`sdetkit verify change --network deny`: the change's code reaches nothing but its own loopback."""

from __future__ import annotations

import functools
import json
import shutil
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from sdetkit import change_verifier, network_boundary

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


@functools.cache
def _isolation() -> str:
    """Why this machine cannot isolate the network, or "" when it can."""

    boundary = network_boundary.assess_network_boundary(require_network_isolation=True)
    if boundary.get(network_boundary.PROOF_EXECUTION_ALLOWED) is True:
        return ""
    return network_boundary.unavailable_reason(boundary)


@pytest.fixture
def isolation() -> None:
    if _isolation():
        pytest.skip(f"no network namespace here: {_isolation()}")


@pytest.fixture
def outside_port() -> Iterator[int]:
    """A server on the host's loopback: reachable from here, not from inside the namespace."""

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    server.settimeout(0.2)
    stop = threading.Event()

    def serve() -> None:
        while not stop.is_set():
            try:
                connection, _ = server.accept()
            except OSError:
                continue
            connection.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield int(server.getsockname()[1])
    stop.set()
    thread.join(timeout=2)
    server.close()


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _python_repo(tmp_path: Path, port: int) -> tuple[Path, str]:
    """A repository whose tests pass only without the network, and a fix to verify on it."""

    repo = tmp_path / "repo"
    (repo / "src" / "calc").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "calc" / "__init__.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    (repo / "tests" / "test_calc.py").write_text(
        f"""\
import socket

import pytest

from calc import add


def test_add():
    assert add(2, 3) == 5


def test_reaches_nothing_outside():
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", {port}), timeout=2).close()


def test_has_its_own_loopback():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        socket.create_connection(server.getsockname(), timeout=2).close()
""",
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "calc"\nversion = "0"\n', encoding="utf-8"
    )
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    (repo / "src" / "calc" / "__init__.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    diff = _git(repo, "diff")
    _git(repo, "checkout", "--", ".")
    return repo, diff


def _verify(repo: Path, out: Path, diff: str, **kwargs: object) -> dict[str, object]:
    return change_verifier.verify_change(
        repo_root=repo,
        out_dir=out,
        python=sys.executable,
        patch_text=diff,
        timeout_seconds=120,
        **kwargs,  # type: ignore[arg-type]
    )


def test_with_the_network_denied_the_tests_reach_only_their_own_loopback(
    tmp_path: Path, isolation: None, outside_port: int
) -> None:
    repo, diff = _python_repo(tmp_path, outside_port)

    denied = _verify(repo, tmp_path / "denied", diff, network="deny")
    allowed = _verify(repo, tmp_path / "allowed", diff)

    assert denied["status"] == "VERIFIED", denied["reasons"]
    assert denied["network_isolated"] is True
    assert denied["network"] == {  # type: ignore[comparison-overlap]
        "mode": "deny",
        "backend": network_boundary.UNSHARE_USER_MAP_ROOT_NET,
        "loopback": "own",
    }
    predicate = json.loads(
        (tmp_path / "denied" / "change-verification.predicate.json").read_text(encoding="utf-8")
    )
    assert predicate["network_isolated"] is True
    # With the network, the test that must not reach the host's server does reach it.
    assert allowed["network_isolated"] is False
    assert allowed["tests"]["comparison"]["still_failing"] == [  # type: ignore[index]
        "tests.test_calc::test_reaches_nothing_outside"
    ]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_javascript_tests_run_without_the_network_too(
    tmp_path: Path, isolation: None, outside_port: int
) -> None:
    repo = tmp_path / "repo"
    (repo / "test").mkdir(parents=True)
    (repo / "calc.js").write_text("exports.add = (a, b) => a - b;\n", encoding="utf-8")
    (repo / "test" / "calc.test.js").write_text(
        f"""\
const test = require("node:test");
const assert = require("node:assert");
const net = require("node:net");
const {{ add }} = require("../calc.js");

test("adds", () => assert.strictEqual(add(2, 3), 5));
test("reaches nothing outside", async () => {{
  await assert.rejects(
    new Promise((resolve, reject) =>
      net.connect({outside_port}, "127.0.0.1", resolve).on("error", reject)
    )
  );
}});
""",
        encoding="utf-8",
    )
    (repo / "package.json").write_text(
        json.dumps({"name": "calc", "private": True, "scripts": {"test": "node --test"}}),
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    (repo / "calc.js").write_text("exports.add = (a, b) => a + b;\n", encoding="utf-8")
    diff = _git(repo, "diff")
    _git(repo, "checkout", "--", ".")

    report = _verify(repo, tmp_path / "out", diff, network="deny")

    assert report["status"] == "VERIFIED", report["reasons"]
    assert report["tests"]["runner"] == "node"  # type: ignore[index]
    assert report["network_isolated"] is True


def test_denying_the_network_where_it_cannot_be_isolated_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        change_verifier,
        "assess_network_boundary",
        lambda **_: {
            network_boundary.PROOF_EXECUTION_ALLOWED: False,
            "probe_report": {"candidates": [{"available": False, "executable": "unshare"}]},
        },
    )
    repo, diff = _python_repo(tmp_path, 9)

    with pytest.raises(change_verifier.ChangeError, match="unshare is not installed"):
        _verify(repo, tmp_path / "out", diff, network="deny")
    assert not (tmp_path / "out" / "change-verification.json").exists()


def test_the_isolated_command_runs_the_original_after_raising_the_loopback() -> None:
    boundary = network_boundary.assess_network_boundary(require_network_isolation=True)
    if boundary.get(network_boundary.PROOF_EXECUTION_ALLOWED) is not True:
        pytest.skip("no network namespace here")

    argv = network_boundary.build_loopback_isolated_argv(boundary, ["pytest", "-q"])

    assert argv[1:4] == ["--user", "--map-root-user", "--net"]
    assert argv[4:6] == [sys.executable, "-I"]
    assert argv[-2:] == ["pytest", "-q"]
    assert "0x8914" in argv[7]
