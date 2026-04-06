# Contributing

For the complete workflow, use the repository guide: [`CONTRIBUTING.md`](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/CONTRIBUTING.md).

If this is your first external PR, start with [First contribution quickstart](first-contribution-quickstart.md).

## First trustworthy contribution (docs-first path)

1. Start from [Start here](index.md) and [Release confidence](release-confidence.md) to align language with the core product story.
2. Keep canonical command truth stable in docs:
   - `python -m sdetkit gate fast`
   - `python -m sdetkit gate release`
   - `python -m sdetkit doctor`
3. Do not invent proof (no synthetic benchmarks, customer claims, or fake outputs).
4. Prefer clarification, consolidation, and cross-linking over adding new surfaces.

## What not to change in this docs sprint

- Do not add new product surfaces, kits, bots, workers, or integrations.
- Do not change CLI behavior or command semantics.
- Do not remove deep docs; demote/reorder/reframe instead.

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
