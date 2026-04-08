# First run quickstart (guided canonical path)

Use this page for a guided run of the same canonical first-proof lane.

If you only want the fastest proof with minimal text, use [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md).

## Guided run (5 minutes)

0. Install in the target external repo (skip only if already installed):

```bash
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
```

1. (Optional) Verify CLI wiring:

```bash
python -m sdetkit --help
python -m sdetkit gate --help
```

2. Run fast confidence gate:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

3. Run release gate:

```bash
python -m sdetkit gate release --format json --out build/release-preflight.json
```

4. Run diagnostics:

```bash
python -m sdetkit doctor
```

## Canonical artifact interpretation order

1. Open `build/release-preflight.json` first (`ok`, `failed_steps`, `profile`).
2. If `failed_steps` includes `gate_fast`, open `build/gate-fast.json` (`ok`, `failed_steps`, `profile`).
3. Only then move to raw logs for deep debugging.

This order matches the canonical decoder: [CI artifact walkthrough](ci-artifact-walkthrough.md).

## Optional wrappers (this repository only)

If you are inside this repository and prefer wrappers:

```bash
bash scripts/ready_to_use.sh quick
bash scripts/ready_to_use.sh release
```

External repositories should use direct `python -m sdetkit ...` commands.

## Contract truth model for first-time external runs

- `gate fast` and `gate release` can legitimately fail on first run while still generating trustworthy JSON triage artifacts.
- Trust breaks only when artifacts are missing or malformed.
- Inspect `build/release-preflight.json` and `build/gate-fast.json` before raw logs.

## Next step routing

- Release-confidence model: [Release confidence](release-confidence.md)
- Team rollout: [Adopt SDETKit in your repository](adoption.md)
- Canonical CI flow: [Recommended CI flow](recommended-ci-flow.md)
- Evidence behavior: [Before/after example](before-after-evidence-example.md), [Evidence showcase](evidence-showcase.md)
