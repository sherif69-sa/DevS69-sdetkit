# First run quickstart (guided canonical path)

Use this page for a guided run of the same canonical first-proof lane.

If you only want the fastest proof with minimal text, use [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md).

## Guided run (5 minutes)

0. Install in the target external repo with Python 3.10+ (skip only if already installed):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install sdetkit==1.0.3
```

Alternative for an isolated global CLI: `pipx install sdetkit==1.0.3`.

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

## Beginner troubleshooting for the canonical first path

The first run often fails for practical setup reasons. That is normal.

For `gate fast` and `gate release`, check both:
- `failed_steps` (what failed)
- `recommendations` (what to run next)

The gate commands now include `recommendations` in both terminal output and JSON output. Start there before deeper debugging.

### `python -m sdetkit gate fast`

Common first-run failures:
- **`ruff`, `mypy`, or `pytest` missing**: your environment does not have dev/test tools yet.
  - Run next: `python -m pip install -e .[dev,test]`
  - Then rerun: `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json`
- **`doctor` step failed**: repo health checks found issues.
  - Run next: `python -m sdetkit doctor --format json --out build/doctor.json`
  - Then fix the first failing check and rerun `gate fast`.

### `python -m sdetkit gate release`

Common first-run failures:
- **`doctor_release` failed**: release readiness checks are not satisfied yet.
  - Run next: `python -m sdetkit doctor --release --format json --out build/doctor-release.json`
  - Then fix the first release check and rerun `gate release`.
- **`gate_fast` failed inside release gate**: release gate depends on fast gate passing.
  - Run next: `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json`
  - Then rerun: `python -m sdetkit gate release --format json --out build/release-preflight.json`

### `python -m sdetkit doctor`

Common first-run failures:
- **Not in a virtual environment** (warning in recommendations/hints).
  - Run next: `python -m venv .venv && source .venv/bin/activate`
  - Then rerun: `python -m sdetkit doctor`
- **Missing developer tools** listed in doctor recommendations.
  - Run next: `python -m pip install -e .[dev,test]`
  - Then rerun: `python -m sdetkit doctor --format json --out build/doctor.json`
- **`pyproject.toml` parse error**.
  - Run next: fix the TOML syntax shown by doctor, then rerun `python -m sdetkit doctor`.

If you are unsure what to do first, follow this order:
1. `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json`
2. `python -m sdetkit gate release --format json --out build/release-preflight.json`
3. `python -m sdetkit doctor --format json --out build/doctor.json`

## Next step routing

- Release-confidence model: [Release confidence](release-confidence.md)
- Team rollout: [Adopt SDETKit in your repository](adoption.md)
- Canonical CI flow: [Recommended CI flow](recommended-ci-flow.md)
- Evidence behavior: [Before/after example](before-after-evidence-example.md), [Evidence showcase](evidence-showcase.md)
