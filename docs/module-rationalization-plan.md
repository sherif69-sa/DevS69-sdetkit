# Module Rationalization Plan (P1.1)

Status: Active proposal (v1)
Date: 2026-04-16

## Objective

Reduce long-term maintenance overhead from completion report-era module sprawl while preserving CLI compatibility and historical evidence continuity.

## Current state snapshot

- Detected completion-era Python modules in `src/sdetkit`: **56** files.
- Largest duplicate family: `continuous_upgrade_completion_*` (**11** files).
- Additional repeat families: `optimization_completion_*` and `weekly_review_completion_*` (2 each).

## Rationalization policy

### Decision categories

- **Keep**: retain as-is when module is an active front-door command with clear ownership and non-overlapping purpose.
- **Merge**: consolidate multiple similarly scoped modules into one implementation surface while preserving old command aliases.
- **Archive**: freeze legacy/transition modules behind legacy namespace and remove from default discovery paths.

### Safety rules (must not break enterprise stability)

1. Keep Tier-A command behavior unchanged (`gate`, `doctor`).
2. Use forwarding shims for renamed/merged modules for at least 2 minor releases.
3. Preserve machine-readable outputs for existing commands during migration.
4. Update docs/help surfaces before changing default discoverability.

## Proposed decisions by family

### Merge families (high ROI)

1. `continuous_upgrade_completion_1..11.py`
   - Decision: **Merge** to a single orchestrator module (`continuous_upgrade_completion.py`) with numeric mode selectors.
2. `case_study_prep1..4_completion_*.py`
   - Decision: **Merge** into a unified `case_study_prep_completion.py` with phase selector.
3. `integration_expansion2/3/4_completion_*.py`
   - Decision: **Merge** into `integration_expansion_completion.py` with stage profile.
4. `phase2_*_completion_*.py` + `phase3_*_completion_*.py`
   - Decision: **Merge** into `readiness_transition_completion.py` with named step lanes.
5. `optimization_completion_42.py` + `optimization_completion_46.py`
   - Decision: **Merge** into one optimized completion report lane.
6. `weekly_review_completion_49.py` + `weekly_review_completion_65.py`
   - Decision: **Merge** to one weekly-review completion report implementation.

### Archive candidates (legacy namespace)

Archive from default help/discovery (keep runnable via legacy routing):

- `objection_completion_48.py`
- `partner_outreach_completion_80.py`
- `community_touchpoint_completion_77.py`
- `growth_campaign_completion_81.py`
- `trust_assets_refresh_completion_75.py`
- `trust_faq_expansion_completion_83.py`

Rationale: narrow campaign-specific surfaces with likely overlap in playbook-style flows.

### Keep candidates (for now)

Keep as standalone until usage telemetry indicates safe consolidation:

- `launch_readiness_completion_86.py`
- `release_prioritization_completion_85.py`
- `reliability_completion_47.py`
- `governance_scale_completion_89.py`

Rationale: directly tied to release/governance/reliability decision contexts.

## Compatibility-preserving migration checklist

### Phase A — Inventory and telemetry baseline

- [ ] Export command usage telemetry for all completion report lanes (90-day window).
- [ ] Identify modules with zero/low usage and zero downstream contract dependencies.

### Phase B — Merge implementation with shims

- [ ] Build unified modules for merge families.
- [ ] Keep old module entrypoints as forwarding shims.
- [ ] Add contract tests proving output schema parity for old vs new command paths.

### Phase C — Discovery cleanup

- [ ] Move archive candidates to legacy/hidden listings.
- [ ] Update CLI help and docs taxonomy to reduce default surface area.

### Phase D — Deprecation completion

- [ ] After 2 minor releases, retire shims with migration notice completion.
- [ ] Publish final rationalization report with before/after module count and support cost impact.

## Success criteria

- Completion-era module count reduced by >= 40% without Tier-A behavior changes.
- No CLI contract regressions on migrated commands.
- Help/discovery surface simplified (fewer default/visible transition-era commands).

## Machine-readable plan

See `docs/contracts/module-rationalization-plan.v1.json`.
