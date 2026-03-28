# Cycle 63 validation commands

```bash
python -m sdetkit cycle63-onboarding-activation-closeout --format json --strict
python -m sdetkit cycle63-onboarding-activation-closeout --emit-pack-dir docs/artifacts/cycle63-onboarding-activation-closeout-pack --format json --strict
python scripts/check_onboarding_activation_closeout_contract_63.py --skip-evidence
```
