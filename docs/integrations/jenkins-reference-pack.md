# Jenkins reference pack (Phase 4)

## Goal

Run the same first-proof lane in Jenkins scripted/declarative jobs.

## Pipeline contract

1. Checkout repository.
2. Create/activate `.venv`.
3. Install dependencies.
4. Run `make first-proof-verify`.
5. Archive `build/first-proof/*`.

## Operator outputs

- `first-proof-summary.json`
- `weekly-threshold-check.json`
- `phase3-dependency-radar-*.json` (optional governance lane)
