from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

from sdetkit.atomicio import atomic_write_text, canonical_json_dumps

from .core import run_agent


@dataclass(frozen=True)
class InboundEvent:
    channel: str
    user_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AdapterError(ValueError):
    pass


class ChannelAdapter:
    def normalize(self, payload: dict[str, Any]) -> InboundEvent:
        raise NotImplementedError


class GenericAdapter(ChannelAdapter):
    def normalize(self, payload: dict[str, Any]) -> InboundEvent:
        channel = str(payload.get("channel", "")).strip()
        user_id = str(payload.get("user_id", "")).strip()
        text = str(payload.get("text", "")).strip()
        metadata = payload.get("metadata", {})
        if not channel or not user_id or not text:
            raise AdapterError("generic payload must include non-empty channel, user_id, text")
        if not isinstance(metadata, dict):
            raise AdapterError("generic metadata must be a JSON object")
        return InboundEvent(channel=channel, user_id=user_id, text=text, metadata=metadata)


class TelegramAdapter(ChannelAdapter):
    def __init__(self, *, enable_outgoing: bool = False, simulation_mode: bool = False) -> None:
        self.enable_outgoing = enable_outgoing
        self.simulation_mode = simulation_mode

    def normalize(self, payload: dict[str, Any]) -> InboundEvent:
        message = payload.get("message") or payload.get("edited_message")
        if not isinstance(message, dict):
            raise AdapterError("telegram update missing message object")
        text = str(message.get("text", "")).strip()
        chat = message.get("chat", {})
        user = message.get("from", {})
        user_id = str(chat.get("id") or user.get("id") or "").strip()
        if not text or not user_id:
            raise AdapterError("telegram message must include chat/user id and text")
        metadata: dict[str, Any] = {
            "update_id": payload.get("update_id"),
            "chat_type": chat.get("type"),
            "username": user.get("username"),
            "simulation_mode": self.simulation_mode,
            "outgoing_enabled": self.enable_outgoing,
        }
        return InboundEvent(channel="telegram", user_id=user_id, text=text, metadata=metadata)


class ConversationStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _conversation_path(self, *, channel: str, user_id: str) -> Path:
        safe_channel = channel.replace("/", "_")
        safe_user_id = user_id.replace("/", "_")
        return (
            self.root
            / ".sdetkit"
            / "agent"
            / "conversations"
            / safe_channel
            / f"{safe_user_id}.jsonl"
        )

    def append(
        self, event: InboundEvent, route_result: dict[str, Any], *, captured_at: float
    ) -> Path:
        target = self._conversation_path(channel=event.channel, user_id=event.user_id)
        row = {
            "captured_at": int(captured_at),
            "channel": event.channel,
            "user_id": event.user_id,
            "text": event.text,
            "metadata": event.metadata,
            "route": route_result,
        }
        existing = ""
        if target.exists():
            existing = target.read_text(encoding="utf-8")
        atomic_write_text(
            target, existing + json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
        )
        return target


class DeterministicRateLimiter:
    def __init__(
        self,
        root: Path,
        *,
        capacity: int = 5,
        refill_per_second: float = 1.0,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self.root = root
        self.capacity = max(1, capacity)
        self.refill_per_second = max(0.0, refill_per_second)
        self.time_fn = time_fn or time.time
        self._in_memory: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _counter_path(self, *, channel: str, user_id: str) -> Path:
        safe_channel = channel.replace("/", "_")
        safe_user_id = user_id.replace("/", "_")
        return (
            self.root / ".sdetkit" / "agent" / "rate_limits" / safe_channel / f"{safe_user_id}.json"
        )

    def _load(self, *, channel: str, user_id: str, now: float) -> dict[str, Any]:
        key = f"{channel}:{user_id}"
        if key in self._in_memory:
            return dict(self._in_memory[key])
        path = self._counter_path(channel=channel, user_id=user_id)
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    self._in_memory[key] = payload
                    return dict(payload)
            except ValueError as exc:
                logging.getLogger(__name__).warning(
                    "Failed to load rate limiter state from %s: %s",
                    path,
                    exc,
                )
        seed = {
            "tokens": float(self.capacity),
            "last_refill": float(now),
            "allowed": 0,
            "denied": 0,
        }
        self._in_memory[key] = seed
        return dict(seed)

    def _save(self, *, channel: str, user_id: str, state: dict[str, Any]) -> None:
        key = f"{channel}:{user_id}"
        self._in_memory[key] = dict(state)
        path = self._counter_path(channel=channel, user_id=user_id)
        atomic_write_text(path, canonical_json_dumps(state))

    def allow(self, *, channel: str, user_id: str) -> tuple[bool, dict[str, Any]]:
        with self._lock:
            now = self.time_fn()
            state = self._load(channel=channel, user_id=user_id, now=now)
            elapsed = max(0.0, float(now) - float(state.get("last_refill", now)))
            tokens = min(
                float(self.capacity),
                float(state.get("tokens", 0.0)) + elapsed * self.refill_per_second,
            )
            allowed = bool(tokens >= 1.0)
            if allowed:
                tokens -= 1.0
                state["allowed"] = int(state.get("allowed", 0)) + 1
            else:
                state["denied"] = int(state.get("denied", 0)) + 1
            state["tokens"] = round(tokens, 6)
            state["last_refill"] = float(now)
            self._save(channel=channel, user_id=user_id, state=state)
            return allowed, state


class ToolBridgeError(RuntimeError):
    pass


class ToolBridge:
    def invoke(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class StdioJsonRpcToolBridge(ToolBridge):
    def __init__(
        self,
        *,
        command: list[str],
        enabled: bool = False,
        allowlist: tuple[str, ...] = (),
        timeout_seconds: float = 5.0,
    ) -> None:
        self.command = list(command)
        self.enabled = enabled
        self.allowlist = set(allowlist)
        self.timeout_seconds = timeout_seconds

    def invoke(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise ToolBridgeError("tool bridge is disabled")
        if tool_name not in self.allowlist:
            raise ToolBridgeError(f"tool not allowlisted: {tool_name}")
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
        }
        proc = subprocess.run(
            self.command,
            input=(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n").encode("utf-8"),
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        if proc.returncode != 0:
            raise ToolBridgeError(f"bridge command failed with exit code {proc.returncode}")
        raw = proc.stdout.decode("utf-8").strip()
        if not raw:
            return {"ok": True, "result": None}
        try:
            decoded = json.loads(raw)
        except ValueError as exc:
            raise ToolBridgeError("bridge returned non-json output") from exc
        if not isinstance(decoded, dict):
            raise ToolBridgeError("bridge response must be a json object")
        return decoded


class AgentRouter:
    def __init__(
        self,
        *,
        root: Path,
        config_path: Path,
        rate_limiter: DeterministicRateLimiter,
        conversation_store: ConversationStore,
        tool_bridge: ToolBridge | None = None,
        task_runner: Callable[..., dict[str, Any]] = run_agent,
    ) -> None:
        self.root = root
        self.config_path = config_path
        self.rate_limiter = rate_limiter
        self.conversation_store = conversation_store
        self.tool_bridge = tool_bridge
        self.task_runner = task_runner

    def _wrapped_task(self, event: InboundEvent) -> str:
        return "omnichannel-event " + json.dumps(
            {
                "channel": event.channel,
                "user_id": event.user_id,
                "text": event.text,
                "metadata": event.metadata,
            },
            ensure_ascii=True,
            sort_keys=True,
        )

    def route(self, event: InboundEvent) -> dict[str, Any]:
        allowed, rate_state = self.rate_limiter.allow(channel=event.channel, user_id=event.user_id)
        if not allowed:
            limited_result: dict[str, Any] = {"status": "rate_limited", "rate": rate_state}
            self.conversation_store.append(
                event, limited_result, captured_at=self.rate_limiter.time_fn()
            )
            return limited_result

        task = self._wrapped_task(event)
        record = self.task_runner(
            self.root,
            config_path=self.config_path,
            task=task,
            auto_approve=False,
        )
        result: dict[str, Any] = {
            "status": str(record.get("status", "error")),
            "hash": str(record.get("hash", "")),
            "rate": rate_state,
            "tool_bridge_enabled": bool(getattr(self.tool_bridge, "enabled", False)),
        }
        self.conversation_store.append(event, result, captured_at=self.rate_limiter.time_fn())
        return result


def process_webhook(
    path: str,
    payload: dict[str, Any],
    *,
    router: AgentRouter,
    generic_adapter: GenericAdapter,
    telegram_adapter: TelegramAdapter,
) -> tuple[HTTPStatus, dict[str, Any]]:
    try:
        if path == "/webhook/generic":
            event = generic_adapter.normalize(payload)
        elif path == "/webhook/telegram":
            event = telegram_adapter.normalize(payload)
        else:
            return HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"}
        routed = router.route(event)
        return HTTPStatus.OK, {"ok": True, "result": routed}
    except AdapterError as exc:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}


class _WebhookHandler(BaseHTTPRequestHandler):
    server_version = "sdetkit-agent-serve/1.0"

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise AdapterError("invalid content-length") from exc
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except ValueError as exc:
            raise AdapterError("request body must be valid json") from exc
        if not isinstance(payload, dict):
            raise AdapterError("json body must be an object")
        return payload

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        server = cast(AgentHTTPServer, self.server)
        router = server.router
        generic_adapter = server.generic_adapter
        telegram_adapter = server.telegram_adapter

        try:
            payload = self._read_json()
            status, body = process_webhook(
                self.path,
                payload,
                router=router,
                generic_adapter=generic_adapter,
                telegram_adapter=telegram_adapter,
            )
            self._write_json(status, body)
        except AdapterError as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


class AgentHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        addr: tuple[str, int],
        *,
        router: AgentRouter,
        generic_adapter: GenericAdapter,
        telegram_adapter: TelegramAdapter,
    ) -> None:
        super().__init__(addr, _WebhookHandler)
        self.router = router
        self.generic_adapter = generic_adapter
        self.telegram_adapter = telegram_adapter


class AgentServeApp:
    def __init__(
        self,
        *,
        root: Path,
        config_path: Path,
        host: str = "127.0.0.1",
        port: int = 8787,
        telegram_simulation_mode: bool = False,
        telegram_enable_outgoing: bool = False,
        capacity: int = 5,
        refill_per_second: float = 1.0,
        tool_bridge_enabled: bool = False,
        tool_bridge_allowlist: tuple[str, ...] = (),
        tool_bridge_command: list[str] | None = None,
    ) -> None:
        bridge: ToolBridge | None = None
        if tool_bridge_command:
            bridge = StdioJsonRpcToolBridge(
                command=tool_bridge_command,
                enabled=tool_bridge_enabled,
                allowlist=tool_bridge_allowlist,
            )

        router = AgentRouter(
            root=root,
            config_path=config_path,
            rate_limiter=DeterministicRateLimiter(
                root, capacity=capacity, refill_per_second=refill_per_second
            ),
            conversation_store=ConversationStore(root),
            tool_bridge=bridge,
        )
        self.server = AgentHTTPServer(
            (host, port),
            router=router,
            generic_adapter=GenericAdapter(),
            telegram_adapter=TelegramAdapter(
                simulation_mode=telegram_simulation_mode,
                enable_outgoing=telegram_enable_outgoing,
            ),
        )

    def serve_forever(self) -> None:
        self.server.serve_forever()

    def shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
