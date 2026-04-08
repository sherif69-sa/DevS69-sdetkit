# Blank repo to value in 60 seconds (canonical first proof)

Use this as the canonical first proof in a fresh repository.

If you want the same path with more guidance, use [First run quickstart](ready-to-use.md).

## Canonical first-proof command path

```bash
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

## Expected first artifacts

```text
build/
├── gate-fast.json
└── release-preflight.json
```

Key fields to inspect first:
- `ok`
- `failed_steps`
- `profile`

## Proof acceptance criteria

A first proof is accepted when all of the following are true:
1. `build/gate-fast.json` exists and is valid JSON.
2. `build/release-preflight.json` exists and is valid JSON.
3. Both files expose `ok`, `failed_steps`, and `profile`.
4. `build/release-preflight.json` is reviewed first, then `build/gate-fast.json` if needed.

## What to do if the first run fails

1. Open `build/release-preflight.json` first.
2. If `failed_steps` includes `gate_fast`, open `build/gate-fast.json`.
3. Fix the first failed step category.
4. Re-run the same command path.

For canonical decode rules, use [CI artifact walkthrough](ci-artifact-walkthrough.md).

## Next step after proof

- Guided first run (same path): [First run quickstart](ready-to-use.md)
- Product model: [Release confidence](release-confidence.md)
- Evidence behavior: [Before/after evidence example](before-after-evidence-example.md)
- Real artifact anchor: [Evidence showcase](evidence-showcase.md)
- Team CI rollout: [Recommended CI flow](recommended-ci-flow.md)
