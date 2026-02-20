# Day 18 validation commands

```bash
python -m sdetkit reliability-evidence-pack --format json --strict
python -m sdetkit reliability-evidence-pack --emit-pack-dir docs/artifacts/day18-reliability-pack --format json --strict
python -m sdetkit reliability-evidence-pack --execute --evidence-dir docs/artifacts/day18-reliability-pack/evidence --format json --strict
python scripts/check_day18_reliability_evidence_pack_contract.py
```
