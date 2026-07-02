# Workflow Consolidation Map (P0.2)

Status: Active proposal (v1)
Date: 2026-07-02

## Objective

Reduce workflow fan-out while preserving required-check compatibility, evidence quality, and release safety.

The current baseline is **57 workflow files**. The durable target remains **12 primary workflows** with specialist behavior moved into reusable or scheduled bundles only after parity proof.

## Primary anchors

1. `ci.yml`
2. `quality.yml`
3. `security.yml`
4. `release.yml`
5. `repo-audit.yml`
6. `dependency-review.yml`
7. `pages.yml`
8. `docs-link-check.yml`
9. `weekly-maintenance.yml`
10. `versioning.yml`
11. `enterprise-gate.yml`
12. `top-tier-reporting-sample.yml`

## Enforced inventory model

Every workflow now has exactly one disposition in `docs/contracts/workflow-consolidation-plan.v1.json`:

- primary anchor
- planned bundle member
- retirement candidate requiring parity evidence
- standalone supporting workflow

Compatibility bridges, reusable workflows, and trusted publishers are recorded as metadata because those properties may overlap a workflow's disposition.

The plan currently records:

- 12 primary workflows
- 24 planned bundle members
- 7 retirement candidates
- 14 standalone supporting workflows
- 3 compatibility bridges
- 1 reusable workflow
- 2 trusted publishers

The 57th workflow, `release-candidate.yml`, is explicitly classified as supporting release qualification. It is read-only and does not grant publication authority.

## Overlap evidence

Generate deterministic JSON and Markdown inventories with:

```bash
python scripts/build_workflow_overlap_report.py \
  --out-json build/workflow-overlap/report.json \
  --out-md build/workflow-overlap/report.md
```

The report records, for every workflow:

- triggers
- top-level and job-level permissions
- effective write scopes
- job status names
- uploaded and downloaded artifacts
- pinned actions
- normalized proof commands
- consolidation disposition

It also groups repeated trigger sets, proof commands, actions, and artifact names. Required contexts from `docs/contracts/required-checks.v1.json` are mapped back to their workflow or job evidence.

The report is evidence only. Duplicate commands are candidates for later shadow-mode consolidation, not automatic retirement authority.

## Migration order

1. Record current topology and required checks.
2. Enforce consolidation-plan parity.
3. Stop zero-signal issue creation.
4. Measure duplicate triggers and overlapping proof commands.
5. Introduce one reusable bundle in shadow mode.
6. Retire only after equivalent artifacts and checks are proven.

## Phase A status

- [x] Machine-readable workflow topology and required-check contracts.
- [x] Complete and mutually exclusive disposition coverage for all 57 workflows.
- [x] Zero-finding issue creation prohibited by contract.
- [ ] Run-frequency and failure-rate telemetry.
- [x] Duplicate trigger and proof-command report.
- [ ] First reusable bundle with shadow parity.

## Safety boundary

This phase is reporting-only. It does not remove workflows, rename required checks, change permissions, alter release publishing, or authorize merge.

Validate the plan with:

```bash
python scripts/check_workflow_consolidation_plan.py
```

The checker fails on stale workflow counts, missing classifications, duplicate dispositions, primary-anchor drift, unknown metadata references, and unsafe zero-signal policy.

## Success targets

- Primary workflow count remains at or below 12.
- Duplicate trigger paths decrease by at least 50%.
- CI minutes per merged PR decrease by at least 20%.
- Required-check compatibility and gate coverage do not regress.
- Zero-signal generated issues remain at 0.
