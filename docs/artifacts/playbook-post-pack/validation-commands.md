# Cycle 39 validation commands

```bash
python -m sdetkit playbook-post --format json --strict
python -m sdetkit playbook-post --emit-pack-dir docs/artifacts/playbook-post-pack --format json --strict
python -m sdetkit playbook-post --execute --evidence-dir docs/artifacts/playbook-post-pack/evidence --format json --strict
python scripts/check_playbook_post_contract.py
```
