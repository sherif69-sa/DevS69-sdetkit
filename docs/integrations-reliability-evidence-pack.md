# Reliability evidence pack (Day 18)

Operational recipe for rolling Day 15, Day 16, and Day 17 evidence into one reliability closeout signal.

## Who this pack is for

- Maintainers publishing a weekly reliability summary.
- Engineering leads who need one deterministic pass/fail closeout checkpoint.
- Contributors who need actionable evidence before tagging release candidates.

## Reliability score model

Day 18 score uses weighted Day 15/16 execution quality plus Day 17 stability/velocity.

- Day 15 score weight: 25%
- Day 16 score weight: 25%
- Day 17 velocity score weight: 20%
- Day 17 stability score weight: 20%
- Day 15 pass-rate weight: 5%
- Day 16 pass-rate weight: 5%

## Fast verification commands

```bash
python -m sdetkit reliability-evidence-pack --format json --strict
python -m sdetkit reliability-evidence-pack --emit-pack-dir docs/artifacts/day18-reliability-pack --format json --strict
python -m sdetkit reliability-evidence-pack --execute --evidence-dir docs/artifacts/day18-reliability-pack/evidence --format json --strict
python scripts/check_day18_reliability_evidence_pack_contract.py
```

## Execution evidence mode

`--execute` runs the Day 18 command chain and writes deterministic logs for each command into `--evidence-dir`.

## Closeout checklist

- [ ] Day 15 execution summary is green.
- [ ] Day 16 execution summary is green.
- [ ] Day 17 strict failures list is empty.
- [ ] Reliability score meets minimum threshold.
- [ ] Day 18 pack is attached to closeout notes.
