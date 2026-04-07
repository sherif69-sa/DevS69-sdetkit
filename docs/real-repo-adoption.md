# Real repo adoption proof (canonical fixture)

This page documents one **realistic repository-shaped fixture** that proves the
canonical SDETKit release-confidence path from local execution to CI artifact
review.

It is fixture evidence, not a customer story or benchmark.

## Fixture

Path: `examples/adoption/real-repo/`

The fixture is intentionally small but realistic:

- `pyproject.toml`
- `src/app/__init__.py`
- `src/app/main.py`
- `tests/test_main.py`

## Why this fixture exists

- prove repeatable local execution of the canonical path
- prove CI replay of the same path
- provide truthful, inspectable artifact examples in one place

## Local commands (exact path)

From repository root:

```bash
python -m pip install -e .
cd examples/adoption/real-repo
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
```

## Golden artifacts (checked-in reference)

Path: `artifacts/adoption/real-repo-golden/`

- `gate-fast.json`
- `release-preflight.json`
- `doctor.json`

These files are generated reference artifacts from the fixture. They are not
live CI artifacts.

## Artifact reading order

1. `release-preflight.json` (`ok`, `failed_steps`, `profile`)
2. `gate-fast.json` (`ok`, `failed_steps`, `profile`)
3. `doctor.json` (`ok`, `quality.failed_check_ids`, `recommendations`)

## How to interpret success/failure

- **Success for command execution** means each command produced its artifact.
- **Gate pass** means `ok: true` in the gate artifact.
- **Gate fail** means `ok: false` and `failed_steps` gives the next triage
  target.

The fixture intentionally demonstrates first-run triage behavior where gate
artifacts can fail while still being valid, truthful evidence.

## CI replay mirror

Workflow: `.github/workflows/adoption-real-repo-canonical.yml`

The CI workflow runs the same three commands against the same fixture and
uploads artifacts with the same filenames, plus per-command return code files
(`*.rc`) to make pass/fail interpretation explicit during review.

## Regeneration note

To verify whether checked-in goldens are fresh without rewriting files, run:

```bash
python scripts/regenerate_real_repo_adoption_goldens.py --check
```

To refresh golden artifacts after intentional changes to fixture or gate
behavior, run:

```bash
python scripts/regenerate_real_repo_adoption_goldens.py
```

This helper runs the same canonical commands and copies outputs from
`examples/adoption/real-repo/build/` to `artifacts/adoption/real-repo-golden/`.
