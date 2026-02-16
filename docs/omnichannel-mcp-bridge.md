# Omnichannel + MCP bridge

`sdetkit agent serve` provides a local dependency-free HTTP intake layer that normalizes inbound channel events and routes them into the AgentOS orchestrator.

## Overview

- Inbound webhooks are accepted over local HTTP endpoints.
- Channel adapters normalize request payloads into internal events (`channel`, `user_id`, `text`, `metadata`).
- Routed events are wrapped as conversation-aware `agent run` tasks.
- Conversation traces are persisted to `.sdetkit/agent/conversations/<channel>/<user_id>.jsonl`.
- Per-user deterministic rate limiting applies before routing.
- A minimal MCP-style tool bridge skeleton exists for safe local subprocess JSON-RPC integration.

## Run locally

```bash
sdetkit agent init
sdetkit agent serve --host 127.0.0.1 --port 8787 --telegram-simulation-mode
```

Optional bridge (disabled by default):

```bash
sdetkit agent serve \
  --tool-bridge-enabled \
  --tool-bridge-allow safe.tool \
  --tool-bridge-command python \
  --tool-bridge-command ./scripts/my_jsonrpc_bridge.py
```

## Webhook payload examples

### Generic webhook

`POST /webhook/generic`

```json
{
  "channel": "slack",
  "user_id": "user-42",
  "text": "please run a repo audit",
  "metadata": {
    "thread_ts": "171819.42"
  }
}
```

### Telegram webhook

`POST /webhook/telegram`

```json
{
  "update_id": 123,
  "message": {
    "text": "status",
    "chat": {"id": 999, "type": "private"},
    "from": {"id": 999, "username": "alice"}
  }
}
```

## Security guidance

- The Telegram adapter supports simulation mode for tests and local runs.
- Outgoing Telegram behavior is opt-in and off by default; do not pass secrets in test runs.
- Tool bridge execution is disabled by default.
- Even when enabled, tool invocation is restricted by a strict allowlist.
- Keep bridge commands local and deterministic; avoid untrusted executables.
- Use low rate limits for internet-exposed deployments and terminate TLS at a trusted reverse proxy.
