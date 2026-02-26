# Day 39 validation commands

```bash
python -m sdetkit day39-playbook-post --format json --strict
python -m sdetkit day39-playbook-post --emit-pack-dir docs/artifacts/day39-playbook-post-pack --format json --strict
python -m sdetkit day39-playbook-post --execute --evidence-dir docs/artifacts/day39-playbook-post-pack/evidence --format json --strict
python scripts/check_day39_playbook_post_contract.py
```
