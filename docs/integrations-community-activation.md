# Community activation (Day 25)

Day 25 converts passive roadmap readers into active contributors through a deterministic roadmap-voting and feedback loop.

## Who should run Day 25

- Maintainers preparing priorities for the next sprint or release train.
- DevRel/community managers collecting qualitative and quantitative roadmap feedback.
- Engineering leads that need transparent prioritization signals for backlog decisions.

## Roadmap-voting discussion contract

Day 25 is complete when a public roadmap-voting thread is opened, tagged, and linked from docs so contributors can vote and comment on priority items.

## Launch checklist

```bash
python -m sdetkit community-activation --format json --strict
python -m sdetkit community-activation --emit-pack-dir docs/artifacts/day25-community-pack --format json --strict
python -m sdetkit community-activation --execute --evidence-dir docs/artifacts/day25-community-pack/evidence --format json --strict
python scripts/check_day25_community_activation_contract.py
```

## Feedback triage SLA

- Triage new roadmap votes/comments within 48 hours.
- Label each item as `accepted`, `needs-info`, or `not-now`.
- Publish weekly summary of wins, blockers, and next actions.

## Activation scoring model

Day 25 computes weighted readiness score (0-100):

- Docs contract + command lane completeness: 45 points.
- Discoverability links in README/docs index: 25 points.
- Top-10 roadmap alignment marker coverage: 20 points.
- Evidence-lane readiness for strict validation: 10 points.

## Execution evidence mode

`--execute` runs deterministic Day 25 checks and writes logs to `--evidence-dir` for release review.
