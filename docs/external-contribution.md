# External contribution

External contribution upgrades public contribution pull by spotlighting starter tasks with clear owners, response SLAs, and evidence-ready follow-up.

## Who should run external-contribution

- Maintainers who want more first-time external contributions from open starter tasks.
- DevRel/community owners who promote contributor-friendly backlog slices.
- Engineering leads that need deterministic response and conversion metrics.

## Starter-task spotlight contract

An external-contribution pass means at least 10 starter tasks are publicly spotlighted with labels, acceptance criteria, and explicit maintainer response windows.

## Launch checklist

```bash
python -m sdetkit external-contribution --format json --strict
python -m sdetkit external-contribution --emit-pack-dir docs/artifacts/external-contribution-pack --format json --strict
python -m sdetkit external-contribution --execute --evidence-dir docs/artifacts/external-contribution-pack/evidence --format json --strict
python scripts/check_day26_external_contribution_push_contract.py
```

## First-response SLA

- Respond to new external contribution comments within 24 hours.
- Label every starter-task thread as `accepted`, `needs-info`, or `not-now`.
- Publish weekly conversion summary (opened -> active -> merged).

## Activation scoring model

External-contribution computes a weighted readiness score (0-100):

- Docs contract + command lane completeness: 45 points.
- Discoverability links in README/docs index: 25 points.
- Top-10 roadmap alignment + starter-task language: 20 points.
- Evidence-lane readiness for strict validation: 10 points.

## Execution evidence mode

`--execute` runs deterministic external-contribution checks and writes logs to `--evidence-dir` for release review.
