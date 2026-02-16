# AgentOS security model

AgentOS applies deny-by-default controls for sensitive actions.

## Safety gates

- File writes:
  - Denied unless target is inside repository root and matches write allowlist.
  - Default allowlist is `.sdetkit/agent/workdir`.
- Shell actions:
  - Always approval-gated.
  - Command allowlist is explicit in config; default is empty.
- MCP/tool bridge:
  - Disabled by default.
  - Requires explicit `--tool-bridge-enabled` and `--tool-bridge-allow` entries.

## Operational controls

- Every run emits a structured run record with approvals/denials.
- Omnichannel traffic records append to conversation history and rate-limit state.
- Deterministic report exports support audit evidence and change tracking.

## Verification

Use:

```bash
python -m sdetkit doctor --ascii
```

and verify security-oriented checks remain green.
