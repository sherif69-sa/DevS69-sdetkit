# Contributing

For the complete workflow, use the repository guide: [`CONTRIBUTING.md`](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/CONTRIBUTING.md).

If this is your first external PR, start here first: [First contribution quickstart](first-contribution-quickstart.md).
For real starter task categories, use [Starter work inventory](starter-work-inventory.md).
Maintainers curating newcomer-ready issues can use [Maintainer starter-issue hygiene](maintainer-starter-issue-hygiene.md).

## Generate the first-contribution checklist

```bash
python -m sdetkit first-contribution --format text --strict
python -m sdetkit first-contribution --write-defaults --format json --strict
python -m sdetkit first-contribution --format markdown --output docs/artifacts/first-contribution-checklist-sample.md
```

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
