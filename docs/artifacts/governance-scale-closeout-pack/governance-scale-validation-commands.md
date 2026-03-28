# Cycle 89 validation commands

```bash
python -m sdetkit governance-scale-closeout --format json --strict
python -m sdetkit governance-scale-closeout --emit-pack-dir docs/artifacts/governance-scale-closeout-pack --format json --strict
python scripts/check_governance_scale_closeout_contract.py --skip-evidence
```
