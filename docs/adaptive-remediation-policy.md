# Adaptive remediation policy

Adaptive remediation policy packs make the safe-remediation lane configurable without weakening the review-first safety model. A policy can narrow allowed safe-fix types, require proof outcomes, and cap changed-file scope, but it cannot turn unknown or review-required diagnoses into automatic fixes.

## Default policy

The default policy lives at `config/adaptive_remediation_policy.default.json` and is described by `schemas/adaptive-remediation-policy.schema.json`.

```json
{
  "schema_version": "sdetkit.adaptive.remediation_policy.v1",
  "allowed_safe_fix_types": ["format_only", "ruff_fixable_lint"],
  "max_changed_files": 8,
  "required_proof_outcomes": ["proof_passed"],
  "allow_review_required_auto_fix": false,
  "blocked_auto_source_codes": ["UNKNOWN", "UNKNOWN_REVIEW_REQUIRED"]
}
```

## Commands

Print a policy template:

```bash
python -m sdetkit adaptive remediation-policy template --format json \
  --out config/adaptive_remediation_policy.default.json
```

Validate a safe-fix or assisted patch-plan artifact:

```bash
python -m sdetkit adaptive remediation-policy validate build/sdetkit/safe-fix.json \
  --policy config/adaptive_remediation_policy.default.json \
  --format json \
  --out build/sdetkit/remediation-policy-result.json
```

## Guardrails enforced

| Guardrail | Why it matters |
| --- | --- |
| Allowed safe-fix types | Keeps auto-fix behavior limited to known mechanical lanes such as formatting and narrow Ruff fixes. |
| Required proof outcomes | Requires `proof_passed` as the signoff target before remediation can be considered complete. |
| Changed-file scope | Prevents broad automatic edits by rejecting plans above `max_changed_files`. |
| Blocked source codes | Keeps `UNKNOWN` and `UNKNOWN_REVIEW_REQUIRED` diagnoses out of automatic remediation even if a custom policy tries to allow them. |
| Review-first patch plans | Assisted patch plans must remain dry-run-only and human-owned. |

## Recommendations

The validator emits one of three recommendations:

- `APPROVE` when the policy and plan satisfy all guardrails.
- `REJECT_POLICY` when the policy itself attempts unsafe expansion.
- `REJECT_PLAN` when the plan violates policy limits.

This lane does not execute fixes. It only evaluates whether a remediation plan is allowed to proceed to its existing proof and audit workflow.
