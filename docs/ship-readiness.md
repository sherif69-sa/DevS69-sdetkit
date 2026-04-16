# Ship readiness (`sdetkit ship-readiness`)

`ship-readiness` is a one-command release contract runner for the core path:

1. `gate fast`
2. `gate release`
3. `doctor`
4. `release-readiness`

It emits one summary artifact with go/no-go decision and blockers.

## Quick start

```bash
python -m sdetkit ship-readiness --format text
python -m sdetkit ship-readiness --format json
```

## Production usage

```bash
python -m sdetkit ship-readiness \
  --strict \
  --retries 2 \
  --retry-delay-sec 1 \
  --out-dir build/ship-readiness \
  --format json
```

Optional enterprise lane in same run:

```bash
python -m sdetkit ship-readiness --strict --include-enterprise --format json
```

## Output artifacts

- `build/ship-readiness/ship-readiness-summary.json`
- `build/ship-readiness/logs/01-gate_fast.log` (and one log per step)

Validate contract:

```bash
python scripts/check_ship_readiness_contract.py \
  --summary build/ship-readiness/ship-readiness-summary.json \
  --format json
```

The summary now includes a blocker catalog with `error_kind`, `attempts`, and `return_code` for release-room triage.

Generate a release-room markdown brief from artifacts:

```bash
make release-room
cat build/release-room-summary.md
```

Final pre-merge gate (all readiness + contracts + release-room brief):

```bash
make premerge-release-room
cat build/premerge-release-room-gate.json
```

## Why use this command

Use it when you need one deterministic release-room contract instead of checking separate command outputs manually.
