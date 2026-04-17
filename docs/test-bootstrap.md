# Test Bootstrap Preflight

Use this preflight before running `pytest`, CI quick lanes, or merge verification.

## What it checks

1. **Runtime readiness** (`sdetkit.test_bootstrap_validate`)
   - Python version support (`>= 3.11`)
   - Required test modules importable (`httpx`, `yaml`, `hypothesis`)
2. **Dependency contract** (`sdetkit.test_bootstrap_contract`)
   - Required bootstrap packages are declared across:
     - `requirements-test.txt`
     - `pyproject.toml` (`project.dependencies` + `project.optional-dependencies.test`)

## Recommended commands

```bash
# Contract check (strict)
PYTHONPATH=src python -m sdetkit.test_bootstrap_contract --strict --repo-root .

# Runtime check (strict)
PYTHONPATH=src python -m sdetkit.test_bootstrap_validate --strict

# One-command merge preflight
make merge-ready
```

## Artifact output

Both module commands support `--out`:

```bash
PYTHONPATH=src python -m sdetkit.test_bootstrap_contract --strict --format json --repo-root . --out .sdetkit/out/test-bootstrap-contract.json
PYTHONPATH=src python -m sdetkit.test_bootstrap_validate --strict --format json --out .sdetkit/out/test-bootstrap-runtime.json
```

## Exit-code contract

- `0`: check passed (or non-strict mode with warnings)
- `2`: strict mode failed (missing deps, unsupported runtime, or contract mismatch)

This mirrors CI/quality preflight behavior in `ci.sh` and `quality.sh`.
