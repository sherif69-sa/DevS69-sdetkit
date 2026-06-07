# Scale upgrade validation commands

```bash
python -m sdetkit scale-upgrade-completion --format json --strict
python -m sdetkit scale-upgrade-completion --emit-pack-dir docs/artifacts/scale-upgrade-completion-pack --format json --strict
python scripts/check_scale_upgrade_completion_contract.py --skip-evidence
```
