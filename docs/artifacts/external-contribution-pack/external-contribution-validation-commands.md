# External contribution validation commands

```bash
python -m sdetkit external-contribution --format json --strict
python -m sdetkit external-contribution --emit-pack-dir docs/artifacts/external-contribution-pack --format json --strict
python -m sdetkit external-contribution --execute --evidence-dir docs/artifacts/external-contribution-pack/evidence --format json --strict
python scripts/check_day26_external_contribution_push_contract.py
```
