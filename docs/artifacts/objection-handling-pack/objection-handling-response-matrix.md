# Name 23 objection response matrix

| Objection | Response | Verification command |
| --- | --- | --- |
| This is too heavy for small teams | Start with doctor + repo + security lanes only. | `python -m sdetkit doctor --json` |
| We already have scripts | Keep scripts, then enforce deterministic strict gates + artifacts with sdetkit. | `python -m sdetkit objection-handling --format json --strict` |
| How do we prove readiness? | Emit Name 23 FAQ pack and attach evidence summary in release review. | `python -m sdetkit objection-handling --emit-pack-dir docs/artifacts/objection-handling-pack --format json --strict` |
