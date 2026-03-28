# Cycle 87 validation commands

```bash
python -m sdetkit governance-handoff-closeout --format json --strict
python -m sdetkit governance-handoff-closeout --emit-pack-dir docs/artifacts/governance-handoff-closeout-pack --format json --strict
python scripts/check_governance_handoff_closeout_contract.py --skip-evidence
```
