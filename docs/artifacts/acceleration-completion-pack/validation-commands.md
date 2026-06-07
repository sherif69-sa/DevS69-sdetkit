# Acceleration validation commands

```bash
python -m sdetkit acceleration-completion --format json --strict
python -m sdetkit acceleration-completion --emit-pack-dir docs/artifacts/acceleration-completion-pack --format json --strict
python scripts/check_acceleration_completion_contract.py --skip-evidence
```
