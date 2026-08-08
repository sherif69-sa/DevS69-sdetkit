# Workflow permission review control plane

The workflow permission review control plane turns the read-only `workflow-governance-report` permission findings into a deterministic, exact-workflow human review queue.

It is intentionally evidence-only. It does not mutate workflow YAML, reduce permissions automatically, authorize merges, dismiss security findings, or treat an existing Markdown decision document as automatic authority.

## Generate the control plane

```bash
python -m sdetkit.workflow_permission_review_control_plane \
  --root . \
  --out build/sdetkit/workflow-permission-review-control-plane.json \
  --markdown-out build/sdetkit/workflow-permission-review-control-plane.md
```

The generated queue is derived from the same `permission_review_evidence_packet.review_tasks` emitted by `workflow-governance-report`.

## Freshness check

```bash
python -m sdetkit.workflow_permission_review_control_plane \
  --root . \
  --out build/sdetkit/workflow-permission-review-control-plane.json \
  --check-freshness \
  --format text
```

Freshness is bound to:

- the current workflow-governance input digest;
- the control-plane generator source;
- `docs/contracts/workflow-permission-review-control-plane.v1.json`;
- every Markdown file under `docs/ci/workflow-permission-review-cards/`;
- every Markdown file under `docs/ci/workflow-permission-decisions/`.

Each queue entry is also bound to the exact SHA-256 digest of the corresponding workflow file.

## Review queue entry

Each permission review task records:

- stable `review_id` derived from the workflow path;
- exact workflow path and SHA-256 digest;
- permission group;
- currently detected write scopes;
- inferred permission reasons from the governance report;
- required human evidence;
- allowed reviewer decisions: `keep`, `reduce`, `split`, or `defer`;
- existing decision-document references that mention the workflow;
- proof contract;
- rollback contract;
- a false authority boundary for automation, patch application, merge, security dismissal, semantic equivalence, and workflow mutation.

## Decision evidence is not automatic authority

A Markdown file under `docs/ci/workflow-permission-decisions/` may contain a real scoped repository-owner decision. The control plane records that file as `decision_evidence_present`, but deliberately keeps:

```text
human_decision_recorded=false
human_decision=null
proposed_change=null
safe_to_patch=false
```

This prevents a broad parser from turning historical or differently scoped prose into permission-change authority.

A permission-only implementation PR is allowed only after the applicable human review record explicitly identifies the exact workflow, current workflow digest or source revision, concrete decision, proposed permission-only change, proof, and rollback.

## Current permission groups

The governance report currently organizes permission review into five product groups:

1. `repository_mutation`
2. `security_upload`
3. `pr_issue_interaction`
4. `deployment_or_oidc`
5. `release_or_provenance`

The control plane does not assume these groups are permanent. It derives the live queue from the current governance report on each run.

## Proof before merge

For control-plane changes, run:

```bash
python -m pytest -q \
  tests/test_workflow_governance_report.py \
  tests/test_workflow_permission_review_control_plane.py \
  -o addopts=
python -m pre_commit run -a
```

Then require exact-head repository CI before merge.

For a later permission-only PR, add workflow-specific execution proof from `docs/ci/workflow-permission-review-playbook.md`. A green control-plane report by itself never proves that a reduced permission set is semantically equivalent.
