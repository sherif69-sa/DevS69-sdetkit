# First run quickstart (canonical)

**Use this page if:** you already installed SDETKit and want the shortest first-run path.

**Not this page:**
- Need install options? Use [Install (canonical)](install.md).
- Need team/CI rollout? Use [Adoption (canonical)](adoption.md) or [Recommended CI flow (canonical)](recommended-ci-flow.md).

## 5-minute first run

1. Verify CLI wiring:

```bash
python -m sdetkit --help
python -m sdetkit gate --help
```

2. Run fast confidence gate:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

3. Run stricter release gate:

```bash
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
```

4. Run environment/release diagnostics:

```bash
python -m sdetkit doctor
```

## How to interpret first artifacts

- `build/gate-fast.json`: check `ok`, then first item in `failed_steps`.
- `build/release-preflight.json`: check `ok` and `failed_steps`; if `gate_fast` failed, start with `build/gate-fast.json`.

For deeper decode rules, use [CI artifact walkthrough (canonical)](ci-artifact-walkthrough.md).

## Optional wrapper lane (this repository only)

If you are inside this repository and prefer wrappers:

```bash
bash scripts/ready_to_use.sh quick
bash scripts/ready_to_use.sh release
```

External repositories should use direct `python -m sdetkit ...` commands.

## Next step routing

- Rolling out to a team repo: [Adopt SDETKit in your repository](adoption.md)
- Implementing CI policy stages: [Recommended CI flow](recommended-ci-flow.md)
- Understanding why this model vs ad hoc scripts: [SDETKit vs ad hoc](sdetkit-vs-ad-hoc.md)
