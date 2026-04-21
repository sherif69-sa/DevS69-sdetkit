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

## Batch completed: report + executive satellite trim

Scoped batch:

- `*-report.md`
- `executive-*.md`
- `cto-*.md`
- `production-*.md`
- `kpi-baseline-week-*.md`
- `repo-*-20*.md`

Action taken:

- expanded `mkdocs.yml` `exclude_docs` patterns for non-primary report families and executive satellites,
- kept canonical user pathways in nav unchanged,
- preserved explicit exceptions (for example `integrations-and-extension-boundary.md`).

Expected outcome:

- lower warning noise in `mkdocs build` output,
- clearer separation between primary operator docs and historical/report satellites.

## Batch completed: operational playbook promotion

Scoped batch:

- `primary-docs-map.md`
- `test-bootstrap.md`
- `real-repo-adoption.md`
- `operator-onboarding-wizard.md`

Action taken:

- promoted these pages into `mkdocs.yml` navigation under `Advanced > Execution programs`,
- kept existing canonical entrypoints intact while improving operator discoverability.

Expected outcome:

- fewer warning-only pages in `mkdocs build` output for operational docs,
- faster navigation to execution-critical runbooks.
