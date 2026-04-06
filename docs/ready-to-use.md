# First run quickstart (canonical guided run)

Use this page if you already installed SDETKit and want a guided first run with interpretation steps.

If you only want the fastest proof first, use [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md).

## Guided first run (5 minutes)

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
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
```

4. Run diagnostics:

```bash
python -m sdetkit doctor
```

## How to read the first artifacts

Start with these files:
- `build/release-preflight.json`
- `build/gate-fast.json`

Check these keys first:
- `ok`
- `failed_steps`
- `profile`

For deeper decode rules, use [CI artifact walkthrough (canonical)](ci-artifact-walkthrough.md).

## Optional wrappers (this repository only)

If you are inside this repository and prefer wrappers:

```bash
bash scripts/ready_to_use.sh quick
bash scripts/ready_to_use.sh release
```

External repositories should use direct `python -m sdetkit ...` commands.

## Next step routing

- Release-confidence model: [Release confidence](release-confidence.md)
- Team rollout: [Adopt SDETKit in your repository](adoption.md)
- CI policy stages: [Recommended CI flow](recommended-ci-flow.md)
- Evidence behavior: [Before/after example](before-after-evidence-example.md), [Evidence showcase](evidence-showcase.md)
