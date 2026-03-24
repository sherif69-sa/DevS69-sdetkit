# Name 26 validation commands

```bash
python -m sdetkit external-contribution-push --format json --strict
python -m sdetkit external-contribution-push --emit-pack-dir docs/artifacts/name26-external-contribution-pack --format json --strict
python -m sdetkit external-contribution-push --execute --evidence-dir docs/artifacts/name26-external-contribution-pack/evidence --format json --strict
python scripts/check_name26_external_contribution_push_contract.py
```
