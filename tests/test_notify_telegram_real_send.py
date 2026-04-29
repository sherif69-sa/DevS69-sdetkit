from __future__ import annotations

import json

from sdetkit import cli, notify_plugins


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_telegram_configured_default_stays_offline(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SDETKIT_TELEGRAM_TOKEN", "token")
    monkeypatch.setenv("SDETKIT_TELEGRAM_CHAT_ID", "123")

    rc = cli.main(["notify", "telegram", "--message", "hello"])

    assert rc == 0
    assert "use --real-send" in capsys.readouterr().out


def test_telegram_real_send_posts_message(monkeypatch, capsys) -> None:
    calls: list[tuple[str, bytes | None]] = []

    def fake_urlopen(req, timeout):  # noqa: ANN001
        calls.append((req.full_url, req.data))
        assert timeout == 10.0
        return _Response({"ok": True, "result": {"message_id": 1}})

    monkeypatch.setenv("SDETKIT_TELEGRAM_TOKEN", "token")
    monkeypatch.setenv("SDETKIT_TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(notify_plugins.request, "urlopen", fake_urlopen)

    rc = cli.main(["notify", "telegram", "--message", "hello", "--real-send"])

    assert rc == 0
    assert "telegram message sent" in capsys.readouterr().out
    assert calls
    url, data = calls[0]
    assert url == "https://api.telegram.org/bottoken/sendMessage"
    assert data is not None
    assert b"chat_id=123" in data
    assert b"text=hello" in data


def test_telegram_real_send_requires_message(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SDETKIT_TELEGRAM_TOKEN", "token")
    monkeypatch.setenv("SDETKIT_TELEGRAM_CHAT_ID", "123")

    rc = cli.main(["notify", "telegram", "--real-send"])

    assert rc == 2
    assert "requires --message" in capsys.readouterr().out


def test_telegram_real_send_handles_api_failure(monkeypatch, capsys) -> None:
    def fake_urlopen(req, timeout):  # noqa: ANN001
        return _Response({"ok": False, "description": "chat not found"})

    monkeypatch.setenv("SDETKIT_TELEGRAM_TOKEN", "token")
    monkeypatch.setenv("SDETKIT_TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(notify_plugins.request, "urlopen", fake_urlopen)

    rc = cli.main(["notify", "telegram", "--message", "hello", "--real-send"])

    assert rc == 2
    assert "chat not found" in capsys.readouterr().out


def test_whatsapp_real_send_is_explicitly_not_implemented(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SDETKIT_WHATSAPP_API_KEY", "key")

    rc = cli.main(["notify", "whatsapp", "--message", "hello", "--real-send"])

    assert rc == 2
    assert "not implemented" in capsys.readouterr().out
