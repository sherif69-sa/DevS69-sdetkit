# Docs navigation cleanup progress

This sprint keeps the **primary docs map hard-limit** intact while reducing MkDocs nav warning noise in a scoped batch.

## Policy guard

Primary pathway policy remains anchored by:

- `docs/primary-docs-map.md`
- `python scripts/check_primary_docs_map.py --format json`

## Batch completed: reports domain

Scoped batch: historical report files (`big-upgrade-report-*`, `ultra-upgrade-report-*`).

Action taken:

- moved these files out of MkDocs warning scope via `exclude_docs` patterns,
- kept canonical pathways and current-reference nav unchanged.

### Measurable reduction

Using `mkdocs build` warning output inventory:

- before batch: report-family warnings present for this domain,
- after batch: report-family warnings reduced to **0**.

## Remaining inventory

Remaining warning inventory is now mostly non-report standalone pages that are intentionally outside primary pathways and should be triaged in future batches.

## Next cleanup batch candidates

1. product strategy/positioning satellite pages
2. deep operational reference satellites
3. archive taxonomy normalization

## Batch completed: automation/agent-os satellites

Scoped batch:

- `agentos-*`
- `automation-templates-engine.md`

Action taken:

- moved this cluster to `exclude_docs` so warning inventory stays focused on active navigation pathways.
