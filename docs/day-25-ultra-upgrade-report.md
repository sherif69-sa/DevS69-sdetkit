# Day 25 ultra upgrade report — community activation closeout

## What shipped

- Added `community-activation` command to enforce roadmap-voting and feedback-triage readiness.
- Added strict docs-contract checks for Day 25 community activation guidance.
- Added deterministic artifact pack + execution evidence mode.
- Added dedicated contract validation script and tests.

## Key command paths

```bash
python -m sdetkit community-activation --format json --strict
python -m sdetkit community-activation --emit-pack-dir docs/artifacts/day25-community-pack --format json --strict
python -m sdetkit community-activation --execute --evidence-dir docs/artifacts/day25-community-pack/evidence --format json --strict
python scripts/check_day25_community_activation_contract.py
```

## Closeout criteria

- Day 25 score >= 90 with no critical failures.
- Integration page includes all required sections + command contract.
- README/docs index discoverability links in place.
- Evidence bundle generated and review-ready.
