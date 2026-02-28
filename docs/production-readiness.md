# Production readiness command (`sdetkit production-readiness`)

Use this command to score whether the repository is ready for a company-grade engineering team to start execution immediately.

## Why this exists

This command gives a **single readiness score** and validates core production expectations:

- Governance docs are present.
- Baseline engineering files exist.
- CI/quality/security workflows exist.
- Package + test layout is ready.
- Reproducibility lockfiles are present.

## Quick run

```bash
python -m sdetkit production-readiness --format text
```

## Strict gate (for CI)

```bash
python -m sdetkit production-readiness --format json --strict
```

When `--strict` is enabled, command exits non-zero if strict readiness is not met.

## Export a shareable artifact pack

```bash
python -m sdetkit production-readiness \
  --format markdown \
  --emit-pack-dir docs/artifacts/production-readiness-pack
```

Generated artifacts:

- `docs/artifacts/production-readiness-pack/production-readiness-summary.json`
- `docs/artifacts/production-readiness-pack/production-readiness-report.md`

## Recommended workflow

1. Run the readiness check at least weekly.
2. Track score trend in release planning.
3. Resolve failed checks before major release milestones.
4. Pair this with the [Production S-class tier blueprint](production-s-class-90-day-boost.md) for 90-day execution planning.
