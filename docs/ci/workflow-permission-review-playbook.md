# Workflow permission review playbook

This playbook supports `sdetkit workflow-governance-report` permission findings.

The report is advisory-only. It does not authorize automatic permission reduction, workflow mutation, security dismissal, merge, or semantic-equivalence claims.

## Review rule

When a workflow is flagged with `permissions_least_privilege` and `safe_to_patch=false`, treat it as a human review task.

Do not reduce permissions unless a reviewer proves all of the following:

1. The workflow job does not use the write scope directly.
2. The workflow job does not call a script, action, `gh`, GitHub API, SARIF upload, Pages deploy, release, attestation, OIDC provider, or repository mutation path that needs the write scope.
3. The workflow still passes focused proof after a tiny permission-only change.
4. The PR changes only the reviewed permission slice.
5. The rollback is a single workflow revert.

## Permission review groups

The workflow governance report groups permission findings into these review buckets:

- `pr_issue_interaction`: issue or pull request comments/reviews/updates.
- `repository_mutation`: branch, content, release, or repository write paths.
- `security_upload`: SARIF or code-scanning upload surfaces.
- `deployment_or_oidc`: Pages or OIDC deployment/provider surfaces.
- `release_or_provenance`: release, provenance, attestation, or OIDC release surfaces.
- `other_write_scope`: write scopes that need manual classification.

These groups are not approvals. They are triage queues for human review.

## Required evidence for a permission PR

For every reviewed workflow, include:

- workflow path
- current granted write scopes
- inferred permission reasons from the report
- exact scope proposed for removal, if any
- exact proof command
- rollback plan
- reviewer decision

## Allowed next action

The only allowed next action from this report is:

```text
collect_human_review_evidence
```

## Blocked actions

The report blocks:

- automatic permission reduction
- broad workflow permission sweeps
- security alert dismissal
- merge authorization
- semantic-equivalence claims

## Example review card

```text
workflow=<path>
current_write_scopes=<list>
review_group=<group>
inferred_reasons=<list>
proposed_change=<none|scope removal>
human_reviewer=<name>
proof=<command>
rollback=<single workflow revert>
decision=<keep|reduce|split|defer>
```
