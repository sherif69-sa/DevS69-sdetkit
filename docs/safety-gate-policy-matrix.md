# SafetyGate policy matrix

This page is the Wave B checkpoint for SafetyGate policy.

It records when a FailureVector can become a safe-fix candidate and when it must stay review-first.

Contract file:

- `docs/contracts/safety-gate-policy-matrix.v1.json`

## Global safe-fix requirements

SafetyGate may allow a safe fix only when all of these are true:

- failure class is `formatter_only` or `lint`
- `safe_fix_candidate` is `true`
- risk is `low`
- scope is `pr_owned_only`
- affected files are non-empty
- local repro command is present

## Policy by failure class

| Failure class | Default decision | Allowed files policy | Review-first when |
| --- | --- | --- | --- |
| `formatter_only` | `safe_fix_allowed_if_all_global_conditions_pass` | `affected_files_only` | affected_files is empty, scope is not pr_owned_only, risk is not low, safe_fix_candidate is false, local_repro_command is empty |
| `lint` | `safe_fix_allowed_if_all_global_conditions_pass` | `affected_files_only` | lint is not mechanically fixable, affected_files is empty, scope is not pr_owned_only, risk is not low, safe_fix_candidate is false, local_repro_command is empty |
| `test` | `review_first` | `none` | always in current policy |
| `type` | `review_first` | `none` | always in current policy |
| `dependency` | `review_first` | `none` | always in current policy |
| `merge_conflict` | `review_first` | `none` | always in current policy |
| `unknown` | `review_first` | `none` | always in current policy |

## Global blocked actions

SafetyGate must never authorize:

- deleting or weakening tests
- skipping CI or verifier checks
- editing workflow gates to hide a failure
- modifying files outside `allowed_files`
- automatic patch application
- merge authorization

## Roadmap boundary

Wave B is about safe-fix versus review-first policy.

This matrix does not add workers, cloud services, dashboards, automatic patch application, or merge authorization.

After this matrix is green, the next Wave B PR may expand SafetyGate behavior only if it remains review-first by default and keeps automation blocked.
