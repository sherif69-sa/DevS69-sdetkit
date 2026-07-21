# Formatter policy proposal observation

This capability measures the quality and usefulness of reviewed formatter-only policy proposals before any later execution research is considered.

## Inputs

The reporter accepts a repository-owned observations JSON file. Every reviewed record must bind to:

- the exact formatter policy proposal path and SHA-256 digest;
- the source repository, commit SHA, and pull request number;
- the reviewer identity and RFC3339 review time;
- an explicit decision and reason;
- outcomes for every contracted proposal-quality dimension;
- retained review notes.

The versioned contract is `docs/contracts/formatter-policy-proposal-observation.v1.json`.

## Proposal-quality dimensions

- `exact_evidence_binding`
- `proposal_scope_clarity`
- `proof_plan_actionability`
- `rollback_clarity`
- `authority_boundary_preservation`
- `operator_usefulness`

Each dimension is recorded as `pass`, `fail`, or `not_applicable`. Decisions are `accept`, `reject`, `defer`, or `request_more_evidence`.

## Command

```bash
python -m sdetkit.formatter_policy_proposal_observation \
  --observations docs/evidence/formatter-policy-proposal/reviewed-observations.v1.json \
  --out-dir build/formatter-policy-proposal-observation \
  --format json
```

The command writes:

```text
build/formatter-policy-proposal-observation/formatter-policy-proposal-observation.json
build/formatter-policy-proposal-observation/formatter-policy-proposal-observation.md
```

## Failure behavior

The command fails closed when the contract or observation source is malformed, the proposal path is missing or shadowed, the proposal digest is stale, source identity does not match, a metric is absent, the proposal is not formatter-only, or any denied authority field is expanded.

Outputs must be outside the source evidence directory, and the source observations file is checked for mutation during report generation.

## Current boundary

The report is observation-only. It does not authorize execution, patch application, merge, publication, security dismissal, SafetyGate changes, semantic-equivalence claims, or a broader maturity claim. Reviewed history does not authorize the current change.

The next real step is to review one actual formatter policy proposal and retain its exact source artifact. No reviewed observation should be added from a synthetic test fixture.
