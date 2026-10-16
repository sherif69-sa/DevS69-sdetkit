# Start Here in 5 Minutes (fast path)

If you only have a few minutes, use this page and run the canonical commands exactly in this order.

## Goal

Get a deterministic ship/no-ship signal with machine-readable artifacts in one short loop.

## 5-minute flow

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
```

## What to check first

1. `build/release-preflight.json`:
   - `ok`
   - `failed_steps`
   - `next_action`
2. If `failed_steps` contains `gate_fast`, inspect `build/gate-fast.json`:
   - `ok`
   - `failed_steps`
   - `next_action`
3. If `failed_steps` contains `doctor_release`, inspect `build/doctor.json`:
   - `ok`
   - `quality.failed_check_ids`
   - `next_action`
4. Use terminal logs only after artifact triage.

## Make review explicit (recommended)

Every gate artifact carries the shared verdict (`verdict.decision` is `SHIP`, `REVIEW`, `NOT_RUN` or `NO_SHIP`). Fold the gate results and your required checks into one merge-readiness decision:

```bash
python -m sdetkit verify merge \
  --checks-json checks.json \
  --evidence build/release-preflight.json \
  --evidence build/gate-fast.json \
  --out-dir build/merge-readiness
```

This writes `build/merge-readiness/merge-readiness.json` and `merge-readiness.md`. The most severe verdict decides, so green checks never hide a failed gate. Use the markdown file in PR or release notes so reviewers read evidence, not only command output.

## Troubleshooting (top links)

- First failure triage: [first-failure-triage.md](first-failure-triage.md)
- Adoption troubleshooting: [adoption-troubleshooting.md](adoption-troubleshooting.md)
- Remediation cookbook: [remediation-cookbook.md](remediation-cookbook.md)

## Next steps

- Team rollout + CI: [recommended-ci-flow.md](recommended-ci-flow.md)
- Compact docs map (primary vs secondary vs archive): [docs-map.md](docs-map.md)
