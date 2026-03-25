# Reliability evidence pack

Operational recipe for rolling GitHub Actions onboarding, GitLab CI onboarding, and contribution-quality-report evidence into one reliability-evidence signal.

## Who this pack is for

- Maintainers publishing a weekly reliability summary.
- Engineering leads who need one deterministic pass/fail review checkpoint.
- Contributors who need actionable evidence before tagging release candidates.

## Reliability score model

The reliability score uses weighted GitHub Actions onboarding and GitLab CI onboarding execution quality plus contribution-quality-report stability and velocity.

- GitHub Actions onboarding score weight: 25%
- GitLab CI onboarding score weight: 25%
- Contribution-quality velocity score weight: 20%
- Contribution-quality stability score weight: 20%
- GitHub Actions onboarding pass-rate weight: 5%
- GitLab CI onboarding pass-rate weight: 5%

## Fast verification commands

```bash
python -m sdetkit reliability-evidence-pack --format json --strict
python -m sdetkit reliability-evidence-pack --emit-pack-dir docs/artifacts/reliability-evidence-pack --format json --strict
python -m sdetkit reliability-evidence-pack --execute --evidence-dir docs/artifacts/reliability-evidence-pack/evidence --format json --strict
python scripts/check_reliability_evidence_pack_contract.py
```

## Execution evidence mode

`--execute` runs the reliability-evidence command chain and writes deterministic logs for each command into `--evidence-dir`.

## Closeout checklist

- [ ] GitHub Actions onboarding execution summary is green.
- [ ] GitLab CI onboarding execution summary is green.
- [ ] Contribution-quality-report strict failures are empty.
- [ ] Reliability score meets minimum threshold.
- [ ] Reliability-evidence pack is attached to review notes.
