# Blank repo to value in 60 seconds (canonical first proof)

Use this as the canonical first proof in a fresh repository.


## Canonical first-proof command path

```bash
mkdir my-repo && cd my-repo
git init
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install sdetkit==1.2.0
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

First-run trust is about inspectable outcomes, not guaranteed green status:
- It is valid for `gate fast`/`gate release` to return non-zero on an unprepared blank repo.
- It is **not** valid for commands to fail without JSON artifacts.
- A trustworthy first run always leaves machine-readable triage artifacts with `ok`, `failed_steps`, and `profile`.

## What a blank repository reads

On 2.0 (`main`), `gate fast` in an empty repository exits `0` with the verdict `NOT_RUN`:

```text
reasons: nothing in this repository was checked: no tests, and no ruff or mypy configuration
next_action: Add tests (tests/ or pytest configuration), or configure ruff or mypy in pyproject.toml, then run: python -m sdetkit gate fast
```

The run proved nothing either way, so it is not a `SHIP`. A repository without `pyproject.toml` is not an error: doctor skips the check, so Go, JavaScript and Rust repositories are judged by their own tests. Releases up to 1.2.0 read `NO_SHIP` here, because doctor required `pyproject.toml`.

## What to do if the first run fails

1. Open `build/release-preflight.json` first.
2. If `failed_steps` includes `gate_fast`, open `build/gate-fast.json`.
3. Fix the first failed step category.
4. Re-run the same command path.

For canonical decode rules, use [CI artifact walkthrough](ci-artifact-walkthrough.md).

## Automated proof that this external path stays real

From this repository root, run:

```bash
python -m pytest -q tests/test_external_first_run_contract.py
```

This test creates a temporary blank external repo, installs SDETKit in a clean virtual environment, runs the canonical path, and verifies artifact contracts.

## Next step after proof

- Product model: [Release confidence](release-confidence.md)
- Evidence behavior: [Before/after evidence example](before-after-evidence-example.md)
- Real artifact anchor: [Evidence showcase](evidence-showcase.md)
- Team CI rollout: [Recommended CI flow](recommended-ci-flow.md)
