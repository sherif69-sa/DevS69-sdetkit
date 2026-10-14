from __future__ import annotations

from dataclasses import dataclass

from sdetkit import notify


@dataclass
class _EP:
    name: str
    value: object

    def load(self):
        return self.value


class _EPs:
    def __init__(self, items: list[_EP]) -> None:
        self._items = items

    def select(self, *, group: str):
        return self._items if group == "sdetkit.notify_adapters" else []


class _Record:
    def __init__(self, factory):
        self.factory = factory


def test_entrypoint_adapters_handles_invalid_and_errors(monkeypatch) -> None:
    class Good:
        name = "good"

        def send(self, _args) -> int:
            return 0

    class BadMissingSend:
        name = "bad"

    class BadLoad:
        name = "boom"

        @staticmethod
        def load():
            raise RuntimeError("boom")

    monkeypatch.setattr(
        notify.metadata,
        "entry_points",
        lambda: _EPs([_EP("good", Good), _EP("bad", BadMissingSend), BadLoad()]),
    )

    adapters = notify._entrypoint_adapters()
    assert set(adapters) == {"good"}


def test_adapter_map_merges_entrypoints_and_local_plugins(monkeypatch) -> None:
    class EPAdapter:
        name = "ep"

        def send(self, _args) -> int:
            return 0

    class LocalAdapter:
        name = "local"

        def send(self, _args) -> int:
            return 0

    class InvalidPlugin:
        name = "invalid"

    monkeypatch.setattr(notify, "_entrypoint_adapters", lambda: {"ep": EPAdapter()})
    monkeypatch.setattr(
        notify,
        "discover",
        lambda *_args, **_kwargs: [
            _Record(lambda: LocalAdapter()),
            _Record(lambda: InvalidPlugin()),
            _Record(lambda: (_ for _ in ()).throw(RuntimeError("x"))),
        ],
    )

    adapters = notify._adapter_map()
    assert "stdout" in adapters
    assert "telegram" in adapters
    assert "whatsapp" in adapters
    assert "ep" in adapters
    assert "local" in adapters
    assert "invalid" not in adapters


def test_main_list_help_and_unknown(monkeypatch, capsys) -> None:
    monkeypatch.setattr(notify, "_adapter_map", lambda: {"stdout": object(), "x": object()})

    assert notify.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "stdout" in out
    assert "x" in out

    assert notify.main([]) == 2
    assert "usage:" in capsys.readouterr().out

    assert notify.main(["missing", "--message", "hello"]) == 2
    assert "not installed" in capsys.readouterr().out


def test_main_sends_when_not_dry_run(monkeypatch) -> None:
    called: dict[str, str] = {}

    class Adapter:
        def send(self, args) -> int:
            called["message"] = args.message
            return 7

    monkeypatch.setattr(notify, "_adapter_map", lambda: {"a": Adapter()})
    rc = notify.main(["a", "--message", "ping"])
    assert rc == 7
    assert called == {"message": "ping"}
