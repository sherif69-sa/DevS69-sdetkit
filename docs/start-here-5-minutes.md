# Start Here in 5 Minutes (fast path)

If you only have a few minutes, use this page and run the canonical commands exactly in this order.

## Goal

Get a deterministic ship/no-ship signal with machine-readable artifacts in one short loop.

## 5-minute flow

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

## What to check first

1. `build/release-preflight.json`:
   - `ok`
   - `failed_steps`
2. If `failed_steps` contains `gate_fast`, inspect `build/gate-fast.json`:
   - `ok`
   - `failed_steps`
3. Use terminal logs only after artifact triage.

## Make review explicit (recommended)

Generate a concise reviewer-ready summary from artifacts:

```bash
make gate-decision-summary
```

This writes:
- `build/gate-decision-summary.json`
- `build/gate-decision-summary.md`

Use the markdown file in PR/release notes so teams review evidence, not only command output.

Validate summary contract (recommended for CI/local guardrails):

```bash
make gate-decision-summary-contract
```

## Troubleshooting (top links)

- First failure triage: [first-failure-triage.md](first-failure-triage.md)
- Adoption troubleshooting: [adoption-troubleshooting.md](adoption-troubleshooting.md)
- Remediation cookbook: [remediation-cookbook.md](remediation-cookbook.md)

## Next steps

- Guided first run: [ready-to-use.md](ready-to-use.md)
- Team rollout + CI: [recommended-ci-flow.md](recommended-ci-flow.md)
- Compact docs map (primary vs secondary vs archive): [docs-map.md](docs-map.md)
