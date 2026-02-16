from __future__ import annotations

import json
from pathlib import Path

from sdetkit.agent.omnichannel import (
    AgentRouter,
    ConversationStore,
    DeterministicRateLimiter,
    GenericAdapter,
    InboundEvent,
    StdioJsonRpcToolBridge,
    TelegramAdapter,
    ToolBridgeError,
    process_webhook,
)


def test_webhook_generic_persists_and_routes_without_network(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_runner(root: Path, **kwargs: object) -> dict[str, object]:
        calls.append(str(kwargs.get("task", "")))
        return {"status": "ok", "hash": "abc123"}

    router = AgentRouter(
        root=tmp_path,
        config_path=tmp_path / ".sdetkit/agent/config.yaml",
        rate_limiter=DeterministicRateLimiter(tmp_path, max_tokens=5, refill_per_second=0.0),
        conversation_store=ConversationStore(tmp_path),
        task_runner=fake_runner,
    )

    status, payload = process_webhook(
        "/webhook/generic",
        {
            "channel": "slack",
            "user_id": "u-1",
            "text": "hello world",
            "metadata": {"thread_ts": "x"},
        },
        router=router,
        generic_adapter=GenericAdapter(),
        telegram_adapter=TelegramAdapter(simulation_mode=True),
    )

    assert int(status) == 200
    assert payload["ok"] is True
    assert len(calls) == 1
    assert "omnichannel-event" in calls[0]

    conversation_file = tmp_path / ".sdetkit/agent/conversations/slack/u-1.jsonl"
    lines = conversation_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    persisted = json.loads(lines[0])
    assert persisted["text"] == "hello world"
    assert persisted["route"]["status"] == "ok"


def test_telegram_adapter_normalizes_payload() -> None:
    adapter = TelegramAdapter(simulation_mode=True)
    event = adapter.normalize(
        {
            "update_id": 123,
            "message": {
                "text": "ping",
                "chat": {"id": 99, "type": "private"},
                "from": {"id": 11, "username": "alice"},
            },
        }
    )

    assert event.channel == "telegram"
    assert event.user_id == "99"
    assert event.text == "ping"
    assert event.metadata["simulation_mode"] is True


def test_rate_limiter_denies_and_persists_counters(tmp_path: Path) -> None:
    limiter = DeterministicRateLimiter(
        tmp_path, max_tokens=2, refill_per_second=0.0, time_fn=lambda: 10.0
    )

    first_allowed, _ = limiter.allow(channel="generic", user_id="u1")
    second_allowed, _ = limiter.allow(channel="generic", user_id="u1")
    third_allowed, state = limiter.allow(channel="generic", user_id="u1")

    assert first_allowed is True
    assert second_allowed is True
    assert third_allowed is False
    assert state["denied"] == 1

    counter_path = tmp_path / ".sdetkit/agent/rate_limits/generic/u1.json"
    persisted = json.loads(counter_path.read_text(encoding="utf-8"))
    assert persisted["allowed"] == 2
    assert persisted["denied"] == 1


def test_router_rate_limit_short_circuits_task_runner(tmp_path: Path) -> None:
    calls: list[InboundEvent] = []

    def fake_runner(root: Path, **kwargs: object) -> dict[str, object]:
        calls.append(InboundEvent(channel="x", user_id="y", text=str(kwargs["task"])))
        return {"status": "ok", "hash": "ok"}

    router = AgentRouter(
        root=tmp_path,
        config_path=tmp_path / ".sdetkit/agent/config.yaml",
        rate_limiter=DeterministicRateLimiter(
            tmp_path, max_tokens=1, refill_per_second=0.0, time_fn=lambda: 1.0
        ),
        conversation_store=ConversationStore(tmp_path),
        task_runner=fake_runner,
    )

    ok = router.route(InboundEvent(channel="generic", user_id="u1", text="first"))
    blocked = router.route(InboundEvent(channel="generic", user_id="u1", text="second"))

    assert ok["status"] == "ok"
    assert blocked["status"] == "rate_limited"
    assert len(calls) == 1


def test_tool_bridge_enforces_disabled_and_allowlist() -> None:
    bridge = StdioJsonRpcToolBridge(command=["python", "-c", "print('{}')"], enabled=False)
    try:
        bridge.invoke("safe.tool", {})
    except ToolBridgeError as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("expected disabled bridge to fail")

    allow_bridge = StdioJsonRpcToolBridge(
        command=["python", "-c", "import json; print(json.dumps({'ok':True}))"],
        enabled=True,
        allowlist=("safe.tool",),
    )
    response = allow_bridge.invoke("safe.tool", {"x": 1})
    assert response["ok"] is True

    try:
        allow_bridge.invoke("unsafe.tool", {})
    except ToolBridgeError as exc:
        assert "allowlisted" in str(exc)
    else:
        raise AssertionError("expected allowlist check to fail")
