# Trust signal upgrade (Day 22)

Day 22 tightens trust posture visibility by keeping reliability badges and policy docs obvious for new adopters.

## Who should run Day 22

- Maintainers responsible for external project trust posture.
- Security/compliance reviewers validating governance visibility.
- DevRel contributors preparing launch-ready README and docs snapshots.

## Trust signal inputs

- README badge row for CI, quality, mutation tests, security, and pages.
- Governance docs (`SECURITY.md`, `docs/security.md`, and policy baseline docs).
- Workflow visibility checks for core trust lanes (`security.yml`, `pages.yml`, and `ci.yml`).

## Fast verification commands

```bash
python -m sdetkit trust-signal-upgrade --format json --strict
python -m sdetkit trust-signal-upgrade --emit-pack-dir docs/artifacts/day22-trust-pack --format json --strict
python -m sdetkit trust-signal-upgrade --execute --evidence-dir docs/artifacts/day22-trust-pack/evidence --format json --strict
python scripts/check_day22_trust_signal_upgrade_contract.py
```

## Scoring model

Day 22 computes a weighted trust score (0-100):

- Badge visibility: 50 points
- Policy docs + discoverability links: 30 points
- Workflow + docs index governance visibility: 20 points

`--strict` fails if critical checks are missing or score is below `--min-trust-score`.

## Execution evidence mode

`--execute` runs the Day 22 command chain and writes deterministic logs into `--evidence-dir`.

## Visibility checklist

- [ ] CI/reliability badges are present in README.
- [ ] Security and policy docs are linked from README governance section.
- [ ] Core trust workflows (`ci.yml`, `security.yml`, `pages.yml`) are present.
- [ ] Day 22 trust score summary is emitted for closeout.
