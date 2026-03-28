# Cycle 55 validation commands

```bash
python -m sdetkit contributor-activation-closeout --format json --strict
python -m sdetkit contributor-activation-closeout --emit-pack-dir docs/artifacts/contributor-activation-closeout-pack --format json --strict
python scripts/check_contributor_activation_closeout_contract.py --skip-evidence
```
