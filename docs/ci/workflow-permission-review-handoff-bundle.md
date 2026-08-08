# Workflow permission reviewer handoff bundle

Workflow Permission Reviewer Handoff Bundle v1 creates a deterministic offline evidence package for the workflow-permission items that currently require human action.

It exists after the review worklist and before the human review itself. It makes the evidence portable without turning portability into decision authority.

## Product flow

```text
workflow governance finding
  -> permission review control plane
  -> exact review packet
  -> governance state machine
  -> review worklist
  -> reviewer handoff bundle
  -> human reviewer / Review Session v1
  -> Decision Record v1
  -> non-executable permission change plan
  -> separate reviewed permission-only PR
  -> workflow-specific proof + rollback
```

The handoff bundle is not a review session and is not a decision record. It cannot capture, prefill, recommend, rank, assign, or retain a human decision.

## What is included

For the current active Stage 8 work items, the bundle contains:

- `workflow-permission-review-handoff-manifest.json`;
- `workflow-permission-review-worklist.json`;
- `workflow-permission-review-worklist.txt`;
- `README.md`;
- one exact packet JSON file under `packets/` per active review item;
- one reviewer-readable packet Markdown file under `packets/` per active review item.

Resolved Stage 8 items whose next action is `none` are not added back into active reviewer work.

## Exact active-packet binding

Before export, every active work item must have exactly one current packet with the same:

- review ID;
- workflow path;
- workflow SHA-256;
- permission group;
- packet digest.

The work item and packet must also retain `safe_to_patch=false` and zero authority boundaries. Worklist machine fields for recommendation, priority, assignment, and decision prefill must remain null.

If any active binding is missing, duplicated, stale, or authority-escalated, the bundle status is `blocked` and export is refused.

## Deterministic manifest

The manifest records:

- current Stage 8 and Stage 4 provenance bindings;
- active work-item count;
- packaged packet count;
- deterministic packet references;
- every generated relative path;
- SHA-256 and byte count for every generated artifact;
- bundle digest;
- zero-authority boundary.

The bundle digest is computed from the artifact index, active packet references, integrity reasons, and the current worklist bundle binding. It does not include a reviewer decision or mutable timestamp.

## Export an offline bundle

```bash
python -m sdetkit.workflow_permission_review_handoff_bundle \
  --root . \
  --out-dir build/sdetkit/workflow-permission-review-handoff \
  --format text
```

Repository-local output may only be written beneath `build/`. Relative paths are resolved beneath the explicit `--root` before that boundary is checked.

The destination must be absent or empty. The writer does not silently delete or overwrite an existing reviewer workspace because doing so could destroy retained human evidence.

An explicit absolute directory outside the repository is allowed for operator-controlled evidence export.

## Validate a retained bundle

```bash
python -m sdetkit.workflow_permission_review_handoff_bundle \
  --root . \
  --check-dir build/sdetkit/workflow-permission-review-handoff \
  --fail-on-stale \
  --format json
```

Validation rebuilds the current expected bundle in memory and checks:

- manifest schema/status/summary/provenance;
- current bundle digest;
- packet-reference bindings;
- artifact index;
- expected file set;
- missing files;
- unexpected files;
- exact artifact bytes;
- SHA-256 for every generated artifact;
- zero authority boundary.

Any current workflow, evidence, packet, worklist, lifecycle, decision, or plan drift propagates through the upstream digests and makes the retained bundle stale.

## Human review boundary

The bundle can be copied to a reviewer and inspected offline. It cannot record what the reviewer decided.

After review, the human decision still belongs in the separate Review Session v1 / Decision Record v1 path. A `reduce` or `split` result still requires a separate reviewed permission-only implementation PR with exact execution proof and rollback.

## Authority boundary

The bundle hard-codes false for:

- automation authority;
- commit authority;
- human-decision fabrication;
- implementation authority;
- merge authority;
- reviewer-note fabrication;
- patch application;
- permission mutation;
- reviewer assignment;
- review-priority inference;
- security dismissal;
- semantic equivalence;
- source-tree writes;
- workflow mutation.

The handoff layer packages evidence. It does not perform the review.
