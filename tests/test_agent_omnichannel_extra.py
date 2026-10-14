from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest

from sdetkit.agent.omnichannel import (
    AdapterError,
    AgentRouter,
    ConversationStore,
    DeterministicRateLimiter,
    GenericAdapter,
    StdioJsonRpcToolBridge,
    TelegramAdapter,
    ToolBridgeError,
    process_webhook,
)


def _router(tmp_path: Path) -> AgentRouter:
    return AgentRouter(
        root=tmp_path,
        config_path=tmp_path / ".sdetkit/agent/config.yaml",
        rate_limiter=DeterministicRateLimiter(tmp_path, capacity=1, refill_per_second=0.0),
        conversation_store=ConversationStore(tmp_path),
        task_runner=lambda *a, **k: {"status": "ok", "hash": "h"},
    )


def test_process_webhook_unknown_and_bad_payload(tmp_path: Path) -> None:
    router = _router(tmp_path)
    status, body = process_webhook(
        "/webhook/nope",
        {},
        router=router,
        generic_adapter=GenericAdapter(),
        telegram_adapter=TelegramAdapter(),
    )
    assert status == HTTPStatus.NOT_FOUND

    status2, body2 = process_webhook(
        "/webhook/generic",
        {"channel": "x"},
        router=router,
        generic_adapter=GenericAdapter(),
        telegram_adapter=TelegramAdapter(),
    )
    assert status2 == HTTPStatus.BAD_REQUEST
    assert body2["ok"] is False


def test_adapter_errors_and_rate_limiter_load_fallback(tmp_path: Path) -> None:
    with pytest.raises(AdapterError):
        GenericAdapter().normalize({"channel": "x", "user_id": "u", "text": "t", "metadata": []})
    with pytest.raises(AdapterError):
        TelegramAdapter().normalize({"message": {"text": ""}})

    p = tmp_path / ".sdetkit/agent/rate_limits/c/u.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{bad", encoding="utf-8")
    lim = DeterministicRateLimiter(tmp_path, capacity=1, refill_per_second=0.0, time_fn=lambda: 1.0)
    allowed, state = lim.allow(channel="c", user_id="u")
    assert allowed is True
    assert state["allowed"] == 1


def test_tool_bridge_error_paths(monkeypatch) -> None:
    class _Proc:
        def __init__(self, rc: int, out: bytes):
            self.returncode = rc
            self.stdout = out

    bridge = StdioJsonRpcToolBridge(command=["x"], enabled=True, allowlist=("t",))

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _Proc(1, b""))
    with pytest.raises(ToolBridgeError):
        bridge.invoke("t", {})

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _Proc(0, b"not-json"))
    with pytest.raises(ToolBridgeError):
        bridge.invoke("t", {})

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _Proc(0, b"[]"))
    with pytest.raises(ToolBridgeError):
        bridge.invoke("t", {})
