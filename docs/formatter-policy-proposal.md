# Formatter policy proposal eligibility

This contract is the final review-first slice in the guarded formatter-remediation research ladder. It binds independently verified formatter-only evidence to one provider-verified human approval record and permits the candidate to enter a **human-reviewed policy proposal**.

It does not alter `SafetyGate`, apply a patch, execute on a branch, mutate `main`, authorize merge or publication, dismiss security findings, or prove semantic equivalence.

## Promotion level

```text
candidate_family=formatter_only
promotion_mode=proposal_only
proposal_eligible=true
execution_eligible=false
branch_execution_allowed=false
safe_fix_allowed=false
review_required=true
safety_gate_policy_changed=false
```

Proposal eligibility means a maintainer may review a future policy change using this evidence. It is not runtime or mutation authority.

## Provider-bound approval record

The approval JSON must identify GitHub as the provider, state that the provider verified the reviewer identity, bind the reviewer and timestamp to `approve_proposal`, match the exact repository, PR, source commit, and verifier-report SHA-256, and acknowledge the proposal limitations.

The local contract checks that binding but does not independently re-authenticate GitHub identity.

## Local command

```bash
python -m sdetkit.formatter_policy_proposal \
  --verifier-dir build/formatter-candidate-verifier \
  --approval-record build/formatter-policy-approval.json \
  --contract-json docs/contracts/formatter-policy-proposal.v1.json \
  --out-dir build/formatter-policy-proposal \
  --format json
```

## Outputs

```text
formatter-policy-proposal.json
formatter-policy-proposal.md
```

The command fails closed on stale approval bindings, missing or shadowed evidence, non-formatter families, failed verifier checks, non-review-first trajectories, RepoMemory authority, current-PR decision input, evidence mutation, or any authority expansion.

## Authority boundary

```text
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
publication_authorized=false
security_dismissal_allowed=false
semantic_equivalence_proven=false
```

Dependency, security, release, workflow-permission, public-API, merge-conflict, compiler, linker, unknown, and broad test-logic changes remain review-first.

Any future branch-only execution research requires a distinct product-control issue, isolated branch scope, explicit rollback, independent verification, and a separate human-reviewed PR.
