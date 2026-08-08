# Workflow permission governance state machine

Workflow Permission Governance State Machine v1 is the read-only integrity and lifecycle layer above the permission review, packet, decision, and change-plan surfaces.

It answers one operational question for every governed workflow:

> What exact human action is allowed next, given the current evidence chain?

It does not choose a permission decision, complete an implementation plan, generate workflow YAML, apply a patch, commit, merge, or dismiss security findings.

## End-to-end flow

```text
workflow governance finding
  -> permission review control plane
  -> exact review packet
  -> human Decision Record v1
  -> non-executable permission change plan
  -> future separate permission-only PR
  -> workflow-specific execution proof + rollback
```

The state-machine layer verifies that the retained/current evidence at those boundaries agrees before reporting the next human step.

## Lifecycle states

Each workflow has exactly one lifecycle state and exactly one next human action.

| State | Meaning | Next human action |
| --- | --- | --- |
| `pending_human_review` | No current exact human decision exists. | `complete_human_permission_review` |
| `resolved_keep` | Human decision is `keep`; no change plan is allowed. | `none` |
| `deferred` | Human decision is `defer`; more human evidence is needed later. | `revisit_deferred_permission_review` |
| `implementation_plan_required` | Human decision is `reduce` or `split` and an exact current non-executable change plan exists. | `complete_permission_change_plan` |
| `blocked` | Evidence is missing, stale, duplicated, orphaned, mismatched, or authority-escalating. | `repair_governance_evidence_binding` |

`implementation_plan_required` is not patch readiness. Stage 6 deliberately keeps `safe_to_patch=false` and all implementation/mutation authority false.

## Integrity checks

The state machine fails closed when it sees any of these conditions:

- missing or duplicate review packet for a control-plane review item;
- review ID, workflow path, workflow SHA-256, or permission-group mismatch;
- packet human-decision state inconsistent with the control plane;
- orphan packet not represented in the current control plane;
- change plan for a pending, `keep`, or `defer` decision;
- missing or duplicate change plan for a `reduce`/`split` decision;
- change-plan decision or Decision Record ref mismatch;
- missing retained decision-record binding reported by Stage 6;
- orphan change plan;
- upstream `safe_to_patch` becoming non-false;
- any upstream authority-boundary field becoming non-false.

A blocked state never guesses how to repair evidence. It reports `repair_governance_evidence_binding` and leaves the actual review to a human.

## Generate the live state

```bash
python -m sdetkit.workflow_permission_governance_state_machine \
  --root . \
  --out build/sdetkit/workflow-permission-governance-state.json \
  --format text
```

Repository-local output is restricted to `build/`. Relative output paths are resolved beneath the explicit `--root`, so process CWD cannot redefine the repository write boundary.

## Freshness validation

A retained state index is bound to:

- Stage 7 generator source;
- the Stage 7 contract;
- control-plane input digest;
- review-packet input and bundle digests;
- change-plan input and bundle digests.

Validate a retained index with:

```bash
python -m sdetkit.workflow_permission_governance_state_machine \
  --root . \
  --check-index build/sdetkit/workflow-permission-governance-state.json \
  --fail-on-stale \
  --format json
```

Any upstream workflow, evidence, decision, packet, or plan drift changes the transitive evidence chain and makes retained Stage 7 output stale.

## Current expected repository state

Until real current human permission decisions are retained, every live permission-review item should remain `pending_human_review` with next action `complete_human_permission_review` and no Stage 6 change plan.

That is an operational state report, not a recommendation about which permission decision the reviewer should make.

## Authority boundary

The state machine hard-codes false for:

- automation authority;
- commit authority;
- human-decision fabrication;
- implementation authority;
- merge authority;
- patch application;
- permission mutation;
- security dismissal;
- semantic equivalence;
- source-tree writes;
- workflow mutation.

The product becomes more useful by making evidence transitions explicit, not by silently crossing them.
