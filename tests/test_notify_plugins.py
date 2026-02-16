from __future__ import annotations

from dataclasses import dataclass

from sdetkit import cli, notify


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
        if group == "sdetkit.notify_adapters":
            return self._items
        return []


def test_notify_missing_adapter_is_friendly(capsys) -> None:
    rc = cli.main(["notify", "telegram", "--message", "hello"])
    assert rc == 0
    assert "not installed" in capsys.readouterr().out


def test_notify_loads_stub_adapter(monkeypatch, capsys) -> None:
    class Adapter:
        name = "stub"

        def send(self, args) -> int:
            print(f"sent:{args.message}")
            return 0

    monkeypatch.setattr(notify.metadata, "entry_points", lambda: _EPs([_EP("stub", Adapter)]))
    rc = cli.main(["notify", "stub", "--message", "ping"])
    assert rc == 0
    assert "sent:ping" in capsys.readouterr().out


def test_notify_dry_run_prevents_send(monkeypatch, capsys) -> None:
    class Adapter:
        name = "stub"

        def send(self, args) -> int:
            raise AssertionError("send should not be called in dry-run")

    monkeypatch.setattr(notify.metadata, "entry_points", lambda: _EPs([_EP("stub", Adapter)]))
    rc = cli.main(["notify", "stub", "--message", "ping", "--dry-run"])
    assert rc == 0
    assert "[dry-run]" in capsys.readouterr().out
