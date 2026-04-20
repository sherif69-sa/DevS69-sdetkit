# Workflow Consolidation Map (P0.2)

Status: Active proposal (v1)
Date: 2026-04-16

## Objective

Reduce CI/workflow sprawl while preserving release-safety coverage by moving from many overlapping workflows to a smaller, tiered operating model.

Current inventory: **43 workflows** under `.github/workflows`.

## Target operating model

Move to 12 durable workflows (core + security + release + docs + maintenance), with specialist checks routed through reusable workflows or scheduled jobs.

### Keep as primary anchors

1. `ci.yml` (core PR/push verification)
2. `quality.yml` (quality lane + deeper validation)
3. `security.yml` (security baseline)
4. `release.yml` (release pipeline)
5. `repo-audit.yml` (repo health contract)
6. `dependency-review.yml` (PR dependency risk gate)
7. `pages.yml` (docs publishing)
8. `docs-link-check.yml` (docs integrity)
9. `weekly-maintenance.yml` (scheduled maintenance bundle)
10. `versioning.yml` (version policy automation)
11. `enterprise-gate.yml` (enterprise decision lane)
12. `top-tier-reporting-sample.yml` (portfolio/reporting sample lane)

### Merge into bundles (retire standalone files after migration)

- **Security bots bundle** (merge):
  - `ghas-alert-sla-bot.yml`
  - `ghas-campaign-bot.yml`
  - `ghas-codeql-hotspots-bot.yml`
  - `ghas-metrics-export-bot.yml`
  - `ghas-review-bot.yml`
  - `secret-protection-review-bot.yml`
  - `security-configuration-audit-bot.yml`
  - `security-maintenance-bot.yml`
  - `osv-scanner.yml`
  - `sbom.yml`

- **Dependency automation bundle** (merge):
  - `dependency-audit.yml`
  - `dependency-auto-merge.yml`
  - `dependency-radar-bot.yml`
  - `pre-commit-autoupdate.yml`

- **Platform operations bundle** (merge):
  - `repo-optimization-bot.yml`
  - `runtime-watchlist-bot.yml`
  - `worker-alignment-bot.yml`
  - `workflow-governance-bot.yml`
  - `integration-topology-radar-bot.yml`
  - `maintenance-on-demand.yml`

- **Adoption/comms bundle** (merge):
  - `pr-helper-bot.yml`
  - `pr-quality-comment.yml`
  - `contributor-onboarding-bot.yml`
  - `docs-experience-bot.yml`

### Candidate retire/absorb (after parity check)

- `advanced-github-actions-reference-64.yml` (documentation/reference lane; absorb into docs process)
- `adapter-smoke-bot.yml` (absorb into `ci.yml` matrix or `quality.yml`)
- `adoption-real-repo-canonical.yml` (convert to scheduled job in adoption bundle)
- `premium-gate.yml` (absorb under `quality.yml` strict profile)
- `mutation-tests.yml` (scheduled strict check under quality bundle)
- `kpi-weekly.yml` and `release-readiness-radar-bot.yml` (fold under reporting + enterprise gate cadence)

## Ownership tags (proposed)

- **Platform Engineering:** `ci.yml`, `quality.yml`, `repo-audit.yml`, `versioning.yml`
- **Security Engineering:** `security.yml`, security bots bundle, `dependency-review.yml`
- **Release Engineering:** `release.yml`, `enterprise-gate.yml`
- **Developer Experience / Docs:** `pages.yml`, `docs-link-check.yml`, adoption/comms bundle
- **Program Ops:** `top-tier-reporting-sample.yml`, reporting/radar scheduled jobs

## Phased migration checklist (CI-safe)

### Phase A — Baseline and parity

- [ ] Export run-frequency + failure-rate telemetry for all 43 workflows.
- [ ] Identify duplicate triggers and overlapping job steps.
- [ ] Define reusable workflow templates for security/dependency/ops bundles.

### Phase B — Bundle introduction

- [ ] Add bundled workflows in parallel (no removals yet).
- [ ] Mirror outputs/artifacts from legacy workflows for parity comparison.
- [ ] Run 2-week shadow mode and verify no coverage regressions.

### Phase C — Controlled retirement

- [ ] Retire merged standalone workflows in batches (security -> dependency -> ops -> adoption).
- [ ] Keep rollback tags for each retired workflow file for one minor release.
- [ ] Update all docs, runbooks, and CODEOWNERS references.

### Phase D — Steady-state governance

- [ ] Enforce workflow count budget (target <= 12 primary files).
- [ ] Add quarterly workflow drift review.
- [ ] Require consolidation impact note for every new workflow proposal.

## Success metrics

- Workflow file count reduced from 43 to <= 12 primary anchors.
- Duplicate trigger paths reduced by >= 50%.
- No loss in gate coverage (quality/security/release readiness).
- CI minute spend per merged PR reduced by >= 20% after consolidation.

## Machine-readable plan

See `docs/contracts/workflow-consolidation-plan.v1.json`.
