# Onboarding time upgrade (Day 24)

Day 24 reduces onboarding time-to-first-success and standardizes a deterministic three-minute activation path.

## Who should run Day 24

- Maintainers improving contributor first-run experience.
- DevRel owners preparing launch-ready quick-start docs.
- Team leads reducing setup friction across Linux/macOS/Windows.

## Three-minute success contract

A Day 24 pass means a new contributor can complete environment setup and run one successful `sdetkit` command in under three minutes with no hidden prerequisites.

## Fast path commands

```bash
python -m sdetkit onboarding-time-upgrade --format json --strict
python -m sdetkit onboarding-time-upgrade --emit-pack-dir docs/artifacts/day24-onboarding-pack --format json --strict
python -m sdetkit onboarding-time-upgrade --execute --evidence-dir docs/artifacts/day24-onboarding-pack/evidence --format json --strict
python scripts/check_day24_onboarding_time_upgrade_contract.py
```

## Time-to-first-success scoring

Day 24 computes weighted readiness score (0-100):

- Onboarding command and role/platform coverage: 40 points.
- Discoverability (README + docs index links): 20 points.
- Docs contract and quick-start consistency: 30 points.
- Evidence and strict validation lane: 10 points.

## Execution evidence mode

`--execute` runs the Day 24 validation chain and stores deterministic logs in `--evidence-dir`.

## Closeout checklist

- [ ] `onboarding` command supports role and platform targeting.
- [ ] README links to Day 24 integration and command examples.
- [ ] Docs index links Day 24 report and artifact references.
- [ ] Day 24 onboarding pack emitted with summary + checklist + runbook.
