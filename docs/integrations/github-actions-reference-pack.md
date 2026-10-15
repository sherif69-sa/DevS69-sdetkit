# GitHub Actions reference pack

## Goal

Provide a canonical GitHub Actions flow for first-proof adoption.

## Required workflow steps

1. Checkout source.
2. Setup Python (3.11/3.12/3.13 matrix).
3. Install test/runtime dependencies.
4. Run `make first-proof-verify`.
5. Upload `build/first-proof/*` artifacts.

## Suggested follow-up lanes

- `python -m sdetkit gate release --reuse-fast build/gate-fast.json --format json --out build/gate-release.json`
- `python -m sdetkit diagnose run --log <ci-log> --prove` for a failing job
