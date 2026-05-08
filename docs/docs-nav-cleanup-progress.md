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


## Current-docs navigation slice

This cleanup pass promotes current operator-facing documentation into the MkDocs navigation without trying to absorb the full historical inventory in one change. The intent is to make active docs discoverable while leaving report archives, one-off plans, and timebound closeout material for later curation.

### Scope policy

The current slice is intentionally limited to documents that serve an active reader journey:

- first-proof material that helps a new operator get from install to repeatable evidence
- team adoption material that explains rollout, roles, onboarding, and common adoption paths
- operator evidence material that explains diagnostic surfaces and proof artifacts
- current reference material that defines supported contracts, compatibility, CI status, and integration packs

The slice is not historical reports, dated investor/audit material, old upgrade closeouts, one-off execution plans, or broad archive cleanup. Those documents may still be useful, but they need a separate archive strategy rather than being mixed into the primary nav.

### Added first-proof discoverability

The first-proof path now exposes the docs that help a user move from a blank repo to a reliable first run:

- Day 1 proof starter
- First-failure triage
- First-proof troubleshooting
- First-proof learning database
- First-proof benchmark narrative

This keeps first-run guidance near the existing install, quickstart, guided run, adoption, container runtime, and CI flow pages.

### Added team adoption discoverability

The team adoption section now includes role and rollout docs that were previously built but not visible in navigation:

- Role-based quickstarts
- Platform engineer quickstart
- QA governance quickstart
- Release owner quickstart
- Operator onboarding 7-day plan
- Onboarding optimization
- Adoption examples
- Adoption scorecard
- Adoption troubleshooting
- Small-team adoption walkthrough
- Enterprise platform-team adoption walkthrough
- Example adoption flow
- Pilot to rollout guide
- Proof sprint checklist

This keeps role-specific onboarding beside the team rollout, release-confidence, KPI, and adoption proof pages.

### Added operator evidence discoverability

The operator evidence section now includes current diagnostic and proof surfaces:

- Adaptive review
- Doctor Cortex CLI
- Doctor diagnosis contract
- Doctor prescriptions
- Golden-path health signal
- Proof log

These docs explain how operators interpret diagnostics, prescriptions, adaptive review output, and proof records.

### Added current reference discoverability

The current reference section now includes active contract and integration docs:

- Docs navigation cleanup progress
- Environment compatibility matrix
- Git workflow branch tracking health
- Legacy required status bridge
- Core command contract
- CI cost telemetry contract
- GitHub Actions reference pack
- GitLab CI reference pack
- Jenkins reference pack
- Rollback and remediation examples

These pages are treated as current reference material because they document supported environment assumptions, command contracts, CI expectations, and integration examples.

### Guardrail

The branch adds a regression test that loads `mkdocs.yml`, handles MkDocs Python YAML tags, calculates the built-doc inventory, and checks that the current-doc slice is explicit in `nav`. This prevents these docs from silently falling back into the broad “pages exist but are not included in nav” inventory.

### Remaining inventory

The remaining MkDocs inventory still includes many useful pages, but it is mixed across several categories:

- historical reports
- dated execution plans
- portfolio and investor-readiness material
- migration notes
- support docs
- productization notes
- roadmap artifacts
- archive-like generated closeout packs

Those groups should be handled as separate PRs with their own navigation or archive policy. This pass deliberately avoids turning the whole inventory into primary navigation.
