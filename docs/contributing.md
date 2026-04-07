# Contributing

For the complete workflow, use the repository guide: [`CONTRIBUTING.md`](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/CONTRIBUTING.md).

If this is your first external PR, start with [First contribution quickstart](first-contribution-quickstart.md).

## First trustworthy contribution (safe-first lane)

Use this page as a concise handoff, then follow the detailed path in [`CONTRIBUTING.md`](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/CONTRIBUTING.md#first-trustworthy-contribution).

1. Pick one safe-first change (docs clarification, focused tests, or lint/type hygiene).
2. Keep scope to one issue and one clear outcome.
3. Validate locally before opening your PR.
4. Preserve canonical release-confidence command language in docs/examples:
   - `python -m sdetkit gate fast` — fast local quality gate signal.
   - `python -m sdetkit gate release` — release-readiness preflight evidence.
   - `python -m sdetkit doctor` — environment diagnostics snapshot.
   - Detailed rationale and surrounding guidance: [`CONTRIBUTING.md`](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/CONTRIBUTING.md#canonical-release-confidence-alignment-check).

## What not to change in this docs sprint

- Do not add new product surfaces, kits, bots, workers, or integrations.
- Do not change CLI behavior or command semantics.
- Do not remove deep docs; demote/reorder/reframe instead.
- For your first PR, avoid broad cross-cutting refactors; start with safe starter surfaces first.

## Baseline contributor validation commands

```bash
python -m pre_commit run -a
bash quality.sh cov
mkdocs build
```

## Feature registry governance (for command-surface changes)

If your PR changes top-level commands, tier/stability metadata, examples, or docs/test links, keep registry updates in the same PR.

See: [Feature registry](feature-registry.md).

```bash
python scripts/sync_feature_registry_docs.py
python scripts/check_feature_registry_contract.py
bash quality.sh registry
python -m sdetkit feature-registry --only-core --format table
```
