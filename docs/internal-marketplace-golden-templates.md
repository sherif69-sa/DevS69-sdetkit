# Internal Marketplace & Golden Templates (P2.2)

Status: Active proposal (v1)  
Date: 2026-04-16

## Objective

Define a reusable internal marketplace model for SDETKit adoption bundles and establish a golden-template contract for consistent rollout across teams.

## Packaging model

Each marketplace package should include:

- `template_id` and semantic `version`
- target `persona` (platform engineer, release manager, security owner, service team)
- included artifacts (workflow templates, policy contracts, sample outputs)
- onboarding command path
- ownership and support channel

## Golden template catalog (v1)

1. `golden-core-release-confidence`
   - Focus: canonical gate path + doctor + baseline policy checks.
2. `golden-enterprise-governance`
   - Focus: policy-control catalog + release/security evidence controls.
3. `golden-ci-cost-reliability`
   - Focus: cost telemetry + reliability SLO weekly snapshots.
4. `golden-rollout-ops`
   - Focus: workflow consolidation + module rationalization migration guides.

## Usage contract

### Required lifecycle stages

1. **Draft**: template authored, no production claim.
2. **Candidate**: validated in at least 2 pilot repos.
3. **Approved**: platform governance signoff.
4. **Deprecated**: replacement announced, migration path published.
5. **Retired**: removed from active marketplace after deprecation window.

### Compatibility rules

- Approved templates require backward compatibility for one minor version.
- Breaking changes require a successor template and migration guide.
- Deprecated templates remain installable for at least 2 minor releases.

## Ownership model

- **Template owner:** accountable for template content and updates.
- **Platform reviewer:** validates runtime/cost impact and compatibility.
- **Security reviewer:** validates control and evidence compliance.
- **Release reviewer:** validates rollout readiness and migration quality.

## Rollout model

### Phase 1 — Bootstrap

- Publish catalog with 4 initial templates.
- Run in 2-3 pilot repos per template.

### Phase 2 — Governance

- Promote only templates that meet reliability/cost thresholds.
- Add template health score (adoption count, failure rate, maintenance freshness).

### Phase 3 — Scale

- Make approved templates self-service via internal documentation index.
- Enforce owner assignment and quarterly template review cadence.

## Machine-readable contract

See `docs/contracts/golden-template-catalog.v1.json`.

## Acceptance criteria (P2.2)

- [x] Internal marketplace model documented.
- [x] Golden template catalog documented.
- [x] Usage + lifecycle contract documented.
- [x] Ownership/rollout model documented.
- [x] Machine-readable catalog published.
