# GitLab CI reference pack (Phase 4)

## Goal

Mirror the first-proof lane in GitLab CI with the same artifact contract.

## Minimal pipeline stages

- `setup`: install Python deps
- `first_proof`: run `make first-proof-verify`
- `artifacts`: persist `build/first-proof/*`

## Policy gates

- Fail pipeline on first-proof threshold breach for protected branches.
- Keep local/non-protected branches non-blocking via profile config.
