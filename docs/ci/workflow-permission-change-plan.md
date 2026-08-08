# Workflow permission change plan

Workflow Permission Change Plan v1 is the non-executable implementation-planning layer after a valid retained human permission decision.

It does not decide whether a workflow should change. It does not infer target permissions. It does not generate a YAML patch. It does not edit a workflow. It does not authorize implementation.

## Product flow

```text
workflow-governance-report
  -> permission review control plane
  -> exact review packets
  -> human review session
  -> retained Decision Record v1
  -> permission change plan v1
  -> separate reviewed permission-only PR
  -> workflow-specific execution proof + rollback
```

## Eligibility

A plan may exist only when the current control plane contains exactly one valid current human Decision Record v1 with decision `reduce` or `split`.

The following never create an implementation plan:

- a pending review;
- a generated review packet;
- Markdown review evidence;
- a recommendation;
- `keep`;
- `defer`;
- a stale or conflicting decision record.

If a `reduce` or `split` decision is reported but its exact retained decision-record file cannot be opened and hashed, plan generation fails closed.

## Generate the live plan index

```bash
python -m sdetkit.workflow_permission_change_plan \
  --root . \
  --out build/sdetkit/workflow-permission-change-plans.json \
  --format text
```

With no current `reduce` or `split` decisions, the expected live state is:

```text
status=not_required
change_plan_count=0
implementation_authorized=false
permission_mutation_allowed=false
```

That is the correct state for the repository today. The generator must not convert the existing review recommendations into change plans.

## Exact decision binding

Every plan template is bound to:

- review ID;
- workflow path;
- exact workflow SHA-256;
- permission group;
- human decision (`reduce` or `split`);
- retained Decision Record v1 path;
- exact Decision Record file SHA-256;
- the human-approved `proposed_change` intent;
- current write-scope snapshot;
- proof contract;
- rollback contract;
- plan digest.

The plan-layer input digest is also bound to the current permission-review control-plane input digest, so workflow, evidence, contract, or decision-record changes stale retained planning output transitively.

## Human implementation fields

The generated template deliberately leaves the concrete implementation empty:

```json
{
  "implementation_scope": "permissions_only",
  "top_level_permissions": null,
  "job_permissions": null,
  "implementation_rationale": null,
  "proof_execution_refs": [],
  "rollback_execution_ref": null,
  "human_completion_required": true
}
```

A human engineer must describe the proposed top-level/job permission maps and rationale. Software does not infer them from workflow steps or from the human decision summary.

## Structural validation

The validator accepts permission levels `read`, `write`, and `none` and checks:

- exact current plan binding;
- permissions-only scope;
- a target permission map is present;
- implementation rationale is present;
- no requested `write` scope is new relative to the reviewed current write-scope snapshot;
- proof/rollback reference fields have valid shapes;
- `ready_for_patch=false`;
- `safe_to_patch=false`;
- separate reviewed PR remains required;
- all authority bits remain false.

A structurally valid plan returns `structurally_ready_for_separate_pr`. This wording is intentional: it means the plan may be used as evidence for a future reviewed permission-only PR. It does **not** authorize a patch.

## No write-scope escalation

If the reviewed workflow currently grants:

```text
contents: write
issues: write
```

then a plan may redistribute those write scope classes between workflow/job permission maps, or reduce them to `read`/`none`, but it cannot introduce `packages: write` or another previously absent write scope.

This is a structural anti-escalation rule. It is not a proof that the narrower/split permission layout will preserve workflow behavior.

## Semantic proof remains separate

The plan validator cannot prove semantic equivalence. A future implementation PR must still execute the workflow-specific proof contract, compare outcomes, retain rollback evidence, and pass normal exact-head repository CI.

Therefore these remain false even for a structurally valid plan:

- `implementation_authorized`;
- `safe_to_patch`;
- `patch_application_allowed`;
- `permission_mutation_allowed`;
- `semantic_equivalence_proven`;
- `merge_authorized`.

## Why this layer is useful

Decision Record v1 captures *what the human decided*. Change Plan v1 captures *what an engineer proposes to implement* without conflating the two. That gives reviewers a deterministic audit trail:

```text
human decision bytes
  -> implementation-plan bytes
  -> future patch bytes
  -> execution proof
```

Each boundary can become stale independently and none grants the next boundary automatic authority.
