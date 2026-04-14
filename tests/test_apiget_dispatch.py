from __future__ import annotations

import os

from sdetkit import apiget_dispatch


def test_run_apiget_with_cassette_strips_cassette_flags() -> None:
    calls: list[tuple[str, list[str]]] = []

    def _runner(module: str, args) -> int:
        calls.append((module, list(args)))
        return 0

    rc = apiget_dispatch.run_apiget_with_cassette(
        [
            "apiget",
            "https://x",
            "--cassette",
            "file.json",
            "--cassette-mode=record",
            "--timeout",
            "5",
        ],
        cassette=None,
        cassette_mode=None,
        run_module_main=_runner,
    )
    assert rc == 0
    assert calls == [("sdetkit.apiget", ["https://x", "--timeout", "5"])]


def test_run_apiget_with_cassette_restores_env(monkeypatch) -> None:
    monkeypatch.delenv("SDETKIT_CASSETTE", raising=False)
    monkeypatch.delenv("SDETKIT_CASSETTE_MODE", raising=False)

    def _runner(_module: str, _args) -> int:
        assert os.environ["SDETKIT_CASSETTE"] == "snap.json"
        assert os.environ["SDETKIT_CASSETTE_MODE"] == "replay"
        return 1

    rc = apiget_dispatch.run_apiget_with_cassette(
        ["apiget", "https://x"],
        cassette="snap.json",
        cassette_mode="replay",
        run_module_main=_runner,
    )
    assert rc == 1
    assert "SDETKIT_CASSETTE" not in os.environ
    assert "SDETKIT_CASSETTE_MODE" not in os.environ
