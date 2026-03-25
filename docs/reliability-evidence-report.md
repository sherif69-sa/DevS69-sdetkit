# Reliability evidence report

## Reliability evidence report

Reliability evidence now provides a full **reliability operating lane**: strict docs contracting, deterministic pack emission, and executable evidence logging tied to GitHub Actions onboarding, GitLab CI onboarding, and contribution-quality-report upstream outputs.

## What shipped

- Upgraded `sdetkit reliability-evidence-pack` with reliability-evidence integration-page validation, strict gates, and weighted reliability score aggregation.
- Added `--write-defaults` auto-recovery mode to regenerate a hardened reliability-evidence page.
- Added execution mode (`--execute --evidence-dir --timeout-sec`) that records deterministic command-level logs and summary JSON.
- Expanded emitted pack payloads to include scorecard, checklist, and validation-commands artifact.
- Added stronger reliability-evidence contract checker coverage across README, docs, page, report, artifacts, and evidence.

## Validation commands

```bash
python -m sdetkit reliability-evidence-pack --format text
python -m sdetkit reliability-evidence-pack --format json --strict
python -m sdetkit reliability-evidence-pack --write-defaults --format json --strict
python -m sdetkit reliability-evidence-pack --emit-pack-dir docs/artifacts/reliability-evidence-pack --format json --strict
python -m sdetkit reliability-evidence-pack --execute --evidence-dir docs/artifacts/reliability-evidence-pack/evidence --format json --strict
python scripts/check_reliability_evidence_pack_contract.py
```

## Closeout

Reliability evidence now provides one deterministic reliability score, one strict gate lane, and one artifact/evidence bundle ready for weekly review and release-readiness reviews.
