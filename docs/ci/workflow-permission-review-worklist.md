# Workflow permission review worklist

Workflow Permission Review Worklist v1 is the read-only human workload and handoff layer above the workflow permission governance state machine.

It answers a narrow operational question:

> Which current workflow-permission items still require a human action, and which exact packet should the reviewer inspect?

The worklist does not rank items, recommend a decision, assign a reviewer, prefill a decision, edit workflow YAML, apply a patch, commit, merge, or dismiss security findings.

## Product flow

```text
workflow governance finding
  -> permission review control plane
  -> exact review packet
  -> governance state machine
  -> review worklist
  -> human reviewer / Review Session v1
  -> Decision Record v1
  -> non-executable permission change plan
  -> separate reviewed permission-only PR
  -> workflow-specific execution proof + rollback
```

The worklist is intentionally different from Review Session v1. The worklist reports current human work. A review session is the separate human-entered envelope used only after a reviewer actually makes decisions.

## Work-item lanes

The worklist preserves Stage 7's next-human-action semantics and groups active items into deterministic action lanes:

- `repair_governance_evidence_binding`;
- `complete_human_permission_review`;
- `revisit_deferred_permission_review`;
- `complete_permission_change_plan`.

Items whose Stage 7 action is `none` are omitted from active work and counted as resolved/no-action items.

Blocked or packet-mismatched items are repair-only. The worklist does not guess a repair or silently route them into a decision lane.

## Exact packet binding

Every active item is bound to the current packet by:

- review ID;
- workflow path;
- workflow SHA-256;
- permission group;
- packet digest.

For human-review lanes the work item exposes the packet's current write scopes, descriptive triage signals, required human evidence, retained evidence references, and allowed human decision enum.

Those fields are evidence only. The generated fields `machine_recommendation`, `review_priority`, `reviewer_assignment`, and `decision_prefill` are always `null`.

## Generate the current worklist

```bash
python -m sdetkit.workflow_permission_review_worklist \
  --root . \
  --out build/sdetkit/workflow-permission-review-worklist.json \
  --format text
```

Repository-local output is allowed only under `build/`. A relative path is resolved beneath the explicit `--root` before that boundary is checked, so process CWD cannot redefine the repository write boundary.

An explicit absolute destination outside the repository is allowed for operator-controlled evidence export.

## Validate retained output

```bash
python -m sdetkit.workflow_permission_review_worklist \
  --root . \
  --check-index build/sdetkit/workflow-permission-review-worklist.json \
  --fail-on-stale \
  --format json
```

Freshness binds the worklist generator and contract plus the exact Stage 7 state-machine input/bundle digests and Stage 4 review-packet input/bundle digests. Any upstream workflow, evidence, decision, packet, plan, or lifecycle drift therefore makes retained worklist output stale transitively.

## Review-first boundary

The worklist cannot convert descriptive packet signals into a decision or priority score. Human reviewers may choose their own review order outside this artifact, but the generated worklist itself does not infer urgency or assign ownership.

For a pending review, the allowed decisions remain `keep | reduce | split | defer`, but they are presented only as the existing human decision enum. No choice is selected.

For an implementation-plan item, the worklist reports the existing plan binding and next human action; it still does not make a patch safe. Stage 6 keeps `safe_to_patch=false`, and implementation remains a separate reviewed PR with exact proof and rollback.

## Authority boundary

The worklist hard-codes false for:

- automation authority;
- commit authority;
- human-decision fabrication;
- implementation authority;
- merge authority;
- patch application;
- permission mutation;
- reviewer assignment;
- review-priority inference;
- security dismissal;
- semantic equivalence;
- source-tree writes;
- workflow mutation.

The product becomes more operationally useful by making human work visible without turning visibility into authority.
