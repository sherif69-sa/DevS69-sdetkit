# Day 23 objection response matrix

| Objection | Response | Verification command |
| --- | --- | --- |
| This is too heavy for small teams | Start with doctor + repo + security lanes only. | `python -m sdetkit doctor --json` |
| We already have scripts | Keep scripts, then enforce deterministic strict gates + artifacts with sdetkit. | `python -m sdetkit faq-objections --format json --strict` |
| How do we prove readiness? | Emit Day 23 FAQ pack and attach evidence summary in release review. | `python -m sdetkit faq-objections --emit-pack-dir docs/artifacts/day23-faq-pack --format json --strict` |
