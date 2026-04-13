# Golden-path health signal

This page defines a lightweight health signal for the canonical release-confidence path:

1. `python -m sdetkit gate fast`
2. `python -m sdetkit gate release`
3. `python -m sdetkit doctor`

## Why

Use this to make canonical-path health explicit in CI and docs workflows.

## Generate health artifact

After running the canonical path and producing JSON outputs:

```bash
python scripts/golden_path_health.py \
  --gate-fast build/gate-fast.json \
  --gate-release build/release-preflight.json \
  --doctor build/doctor.json \
  --out .sdetkit/out/golden-path-health.json
```

Exit code behavior:

- `0` => all three artifacts are present and `ok: true`
- `2` => any artifact is missing/invalid/not `ok: true`

## Output contract

`golden-path-health.json` includes:

- `schema_version`
- `canonical_path`
- `overall_ok`
- `checks` (`gate_fast`, `gate_release`, `doctor`) with `state`, `ok`, and `path`
