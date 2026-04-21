# Security model

This repository uses a layered security posture:

1. runtime safety controls (AgentOS)
2. repository security gate (`sdetkit security`)
3. CI regression baseline checks

## Threat model assumptions

- The repository may contain untrusted code changes from contributors and automation.
- CI and local execution should remain offline-capable for core checks.
- Preventing accidental secret leakage and high-risk patterns is prioritized over broad heuristic noise.
- Security checks must be deterministic to support reliable baselines and diffing.

## Default blocked/guarded behavior

AgentOS deny-by-default controls:

- File writes:
  - Denied unless target is inside repository root and matches write allowlist.
  - Default allowlist is `.sdetkit/agent/workdir`.
- Shell actions:
  - Approval-gated with explicit command allowlists.
- MCP/tool bridge:
  - Disabled by default.
  - Requires explicit `--tool-bridge-enabled` and `--tool-bridge-allow` entries.

## Security gate policy behavior

`python -m sdetkit security` enforces red-flag policy for:

- dangerous execution APIs
- insecure deserialization and YAML loading
- weak hashes
- obvious path traversal / unsafe writes
- secret leakage patterns
- network calls without timeouts
- debug prints in `src/` (except for an explicit allowlist of operational CLI modules)

Allowlists:

- inline: `# sdetkit: allow-security <RULE_ID>`
- repo file: `tools/security_allowlist.json`
- module-level debug print exceptions: `PRINT_ALLOWED_MODULE_SUFFIXES` in `src/sdetkit/security_gate.py`

Baseline regression gate:

- baseline file: `tools/security.baseline.json`
- checks fail only on new findings when baseline exists
- checks fail on all violations when baseline is missing

## Verification

```bash
python -m sdetkit security check --baseline tools/security.baseline.json --format text
python -m sdetkit doctor --ascii
```
