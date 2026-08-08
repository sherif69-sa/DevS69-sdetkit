# Workflow permission decision record v1

A workflow permission decision record is strict, machine-readable **human decision evidence** for one exact item in the workflow permission review control plane.

The record changes review state only. It does not mutate workflow YAML, authorize implementation, authorize merge, dismiss security findings, or prove semantic equivalence for a later permission change.

## File location

Decision records live under:

```text
docs/ci/workflow-permission-decisions/*.decision.json
```

Markdown files in the same directory remain supporting evidence only. They are never parsed as authoritative decision records.

## Required binding

A current record must match the live control-plane entry exactly on:

- `review_id`;
- workflow path;
- workflow SHA-256;
- permission group.

If the workflow bytes change, the record becomes stale automatically and the control-plane item returns to pending review.

## Decisions

Allowed decisions are:

- `keep` — retain the current permission shape;
- `reduce` — approve a narrower permission-only change for a separate implementation PR;
- `split` — approve redistribution of existing permission authority to narrower jobs/steps for a separate implementation PR;
- `defer` — record that the current evidence is insufficient and more human review is required.

`keep` and `defer` must use:

```json
{
  "kind": "none"
}
```

for `proposed_change`.

`reduce` and `split` must use a `permission_only` proposed change with a human-readable summary and a GitHub evidence reference.

## Record shape

Example template only; this is not a real decision:

```json
{
  "schema_version": "sdetkit.workflow_permission_decision_record.v1",
  "review_id": "wpr-<exact-review-id>",
  "workflow": ".github/workflows/example.yml",
  "workflow_sha256": "<exact-current-sha256>",
  "permission_group": "security_upload",
  "decision": "split",
  "reviewer": "<human-reviewer>",
  "reviewer_evidence": "https://github.com/<owner>/<repo>/issues/<n>#issuecomment-<id>",
  "decided_at": "2026-08-08T13:30:00+00:00",
  "rationale": "<why this exact decision was made>",
  "proposed_change": {
    "kind": "permission_only",
    "summary": "<narrow permission-only change>",
    "evidence_ref": "https://github.com/<owner>/<repo>/issues/<n>#issuecomment-<id>"
  },
  "proof_contract": [
    "workflow permission contract tests",
    "exact-head CI",
    "workflow-specific execution proof"
  ],
  "rollback_contract": {
    "strategy": "restore_exact_workflow_bytes",
    "workflow_sha256": "<exact-current-sha256>"
  },
  "authority_boundary": {
    "automation_allowed": false,
    "implementation_authorized": false,
    "merge_authorized": false,
    "patch_application_allowed": false,
    "security_dismissal_allowed": false,
    "semantic_equivalence_proven": false,
    "workflow_mutation_allowed": false
  }
}
```

## Validation

Validate the current repository records with:

```bash
python -m sdetkit.workflow_permission_decision_record --root . --format text
```

To fail when any decision record is stale, invalid, or conflicting:

```bash
python -m sdetkit.workflow_permission_decision_record \
  --root . \
  --format text \
  --fail-on-invalid
```

The validator classifies records as:

- `current` — one valid record matches the current review item exactly;
- `stale` — the record is structurally valid but its workflow/rollback digest no longer matches current bytes;
- `invalid` — schema, identity, reviewer, timestamp, change shape, proof, rollback, or authority boundary is invalid;
- `conflict` — more than one current valid record exists for the same workflow. No record wins.

## Control-plane effect

Exactly one current valid record changes its control-plane entry to:

```text
review_state=human_decision_recorded
human_decision_recorded=true
safe_to_patch=false
```

For `reduce` or `split`, the next allowed action becomes `prepare_separate_permission_change_pr`.

That means **prepare a separate reviewed implementation PR**. It is not permission to patch automatically.

Stale, invalid, duplicate/conflicting, unknown-workflow, or Markdown-only evidence never changes `human_decision_recorded` to true.

## Proof and rollback

A later permission-change PR must independently prove the narrowed workflow through the workflow-specific playbook. The decision record cannot replace CI, execution proof, or rollback validation.

The rollback contract preserves the exact pre-change workflow digest so a permission-only implementation can restore the reviewed bytes if the narrowed scope breaks required behavior.
