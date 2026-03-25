# Onboarding optimization validation commands

```bash
python -m sdetkit onboarding-optimization --format json --strict
python -m sdetkit onboarding-optimization --emit-pack-dir docs/artifacts/onboarding-optimization-pack --format json --strict
python -m sdetkit onboarding-optimization --execute --evidence-dir docs/artifacts/onboarding-optimization-pack/evidence --format json --strict
python scripts/check_onboarding_optimization_contract.py
```
