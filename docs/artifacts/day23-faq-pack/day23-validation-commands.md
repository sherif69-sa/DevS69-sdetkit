# Day 23 validation commands

```bash
python -m sdetkit faq-objections --format json --strict
python -m sdetkit faq-objections --emit-pack-dir docs/artifacts/day23-faq-pack --format json --strict
python -m sdetkit faq-objections --execute --evidence-dir docs/artifacts/day23-faq-pack/evidence --format json --strict
python scripts/check_day23_faq_objections_contract.py
```
