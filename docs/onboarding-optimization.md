# Onboarding optimization

Onboarding optimization reduces time-to-first-success and standardizes a deterministic three-minute activation path.

## Who should run onboarding-optimization

- Maintainers improving contributor first-run experience.
- DevRel owners preparing launch-ready quick-start docs.
- Team leads reducing setup friction across Linux/macOS/Windows.

## Three-minute success contract

An onboarding-optimization pass means a new contributor can complete environment setup and run one successful `sdetkit` command in under three minutes with no hidden prerequisites.

## Fast path commands

```bash
python -m sdetkit onboarding-optimization --format json --strict
python -m sdetkit onboarding-optimization --emit-pack-dir docs/artifacts/onboarding-optimization-pack --format json --strict
python -m sdetkit onboarding-optimization --execute --evidence-dir docs/artifacts/onboarding-optimization-pack/evidence --format json --strict
python scripts/check_day24_onboarding_time_upgrade_contract.py
```

## Time-to-first-success scoring

Onboarding-optimization computes a weighted readiness score (0-100):

- Onboarding command and role/platform coverage: 40 points.
- Discoverability (README + docs index links): 20 points.
- Docs contract and quick-start consistency: 30 points.
- Evidence and strict validation lane: 10 points.

## Execution evidence mode

`--execute` runs the onboarding-optimization validation chain and stores deterministic logs in `--evidence-dir`.

## Closeout checklist

- [ ] `onboarding` command supports role and platform targeting.
- [ ] README links to onboarding-optimization integration and command examples.
- [ ] Docs index links the onboarding-optimization report and artifact references.
- [ ] Onboarding-optimization pack emitted with summary, checklist, and runbook.
