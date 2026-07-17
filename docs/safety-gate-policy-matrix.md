# SafetyGate policy matrix

This page is the maintained foundation checkpoint for SafetyGate policy.

It records when a FailureVector can become a safe-fix candidate, when it must stay review-first, which downstream platform layers are already implemented, and which actions remain explicitly unauthorized.

Contract files:

- `docs/contracts/safety-gate-policy-matrix.v1.json`
- `docs/contracts/platform-capability-matrix.v1.json`

## Global safe-fix requirements

SafetyGate may allow a safe-fix candidate only when all of these are true:

- failure class is `formatter_only` or `lint`;
- `safe_fix_candidate` is `true`;
- risk is `low`;
- scope is `pr_owned_only`;
- affected files are non-empty;
- a local repro command is present.

This decision is eligibility only. SafetyGate does not apply a patch, run privileged workflows, authorize merge, publish a release, dismiss a security finding, or prove semantic equivalence.

## Policy by failure class

| Failure class | Default decision | Allowed files policy | Review-first when |
| --- | --- | --- | --- |
| `formatter_only` | `safe_fix_allowed_if_all_global_conditions_pass` | `affected_files_only` | affected_files is empty, scope is not pr_owned_only, risk is not low, safe_fix_candidate is false, local_repro_command is empty |
| `lint` | `safe_fix_allowed_if_all_global_conditions_pass` | `affected_files_only` | lint is not mechanically fixable, affected_files is empty, scope is not pr_owned_only, risk is not low, safe_fix_candidate is false, local_repro_command is empty |
| `test` | `review_first` | `none` | always in current policy |
| `compile` | `review_first` | `none` | always in current policy |
| `link` | `review_first` | `none` | always in current policy |
| `type` | `review_first` | `none` | always in current policy |
| `dependency` | `review_first` | `none` | always in current policy |
| `merge_conflict` | `review_first` | `none` | always in current policy |
| `unknown` | `review_first` | `none` | always in current policy |

Compiler and linker diagnostics may identify likely source ownership and explicit local proof commands, but they remain review-first. They do not become safe-fix candidates merely because the saved evidence is high-confidence.

## Current downstream platform truth

The following layers already compose SafetyGate on `main` and are not future-wave placeholders:

- `TrajectoryStore`
- `RepoMemory`
- `ReplayableBenchmarkHarness`
- `ProtectedVerifier`
- `PatchScorer`
- `PRReporter`
- `local diagnostic queue and worker`

The next lane is **Cross-provider adoption and real-repository evidence**. Future policy promotion must be driven by reviewed trajectories and benchmark/verifier evidence, not by the existence of these components alone.

## Global blocked actions

SafetyGate must never authorize:

- deleting or weakening tests;
- skipping CI or verifier checks;
- editing workflow gates to hide a failure;
- modifying files outside `allowed_files`;
- broad automatic patch application;
- automatic merge authorization;
- automatic security remediation or dismissal;
- automatic release publication;
- hosted service or cloud infrastructure without proven local demand.

## Promotion rule

A narrow mechanical category may be evaluated for guarded remediation only after all of the following are available:

1. repeated reviewed trajectories with a zero false-authority record;
2. replayable no-op, oracle, and unsafe-patch scenarios;
3. ProtectedVerifier scope and anti-cheat proof;
4. exact focused and quality proof commands;
5. easy rollback;
6. PR-owned file scope;
7. human-reviewed policy change.

Unknown, dependency, security, release, public-API, merge-conflict, compiler, linker, and broad test-logic failures remain review-first.
