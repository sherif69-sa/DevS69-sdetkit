# FailureVector support matrix

This page is the maintained foundation checkpoint for the FailureVectorEngine.

It records which failure classes are supported, how they should be treated, which downstream platform layers are already implemented, and which authority remains intentionally denied.

Contract files:

- `docs/contracts/failure-vector-support-matrix.v1.json`
- `docs/contracts/platform-capability-matrix.v1.json`

## Supported failure classes

| Failure class | Default risk | Safe-fix candidate | Review policy | First signal contract |
| --- | --- | --- | --- | --- |
| `test` | `medium` | `False` | `review_or_focused_proof` | structured test identity or assertion failure line |
| `compile` | `medium` | `False` | `review_first` | structured compiler source or header diagnostic |
| `link` | `medium` | `False` | `review_first` | structured linker unresolved or duplicate symbol diagnostic |
| `formatter_only` | `low` | `True` | `mechanical_safe_fix_allowed_when_pr_owned` | ruff format failed or would be reformatted |
| `lint` | `medium` | `only mechanically fixable lint such as I001 import sorting` | `safe_fix_only_for_low_risk_mechanical_lint` | ruff rule line or ruff check signal |
| `type` | `medium` | `False` | `review_first` | mypy file:line error |
| `dependency` | `high` | `False` | `review_first` | pip resolver failure such as ResolutionImpossible |
| `merge_conflict` | `high` | `False` | `review_first` | CONFLICT line or merge conflict signal |
| `unknown` | `high` | `False` | `review_first` | first meaningful wrapper line, not generic exit-code fallback |

C++ saved-evidence normalization supports structured GCC, Clang, selected MSVC, GNU/MSVC linker, CTest, GoogleTest, and Catch2-style failure output. It does not invoke a compiler, linker, build system, or test runner. Local reproduction commands are preserved only when the saved evidence explicitly contains one; the adapter does not invent commands from tool identity alone.

Mixed compiler/linker/test output remains `unknown` with low confidence. Generated, vendored, dependency, and common build-output paths do not create source-ownership claims.

## Current downstream platform truth

The following layers are already present on `main` and must not be repeatedly scheduled as unopened roadmap waves:

- `SafetyGate`
- `TrajectoryStore`
- `RepoMemory`
- `ReplayableBenchmarkHarness`
- `ProtectedVerifier`
- `PatchScorer`
- `PRReporter`
- `local diagnostic queue and worker`

The next lane is **Cross-provider adoption and real-repository evidence**. The platform should now deepen provider coverage, prove mixed-repository journeys, and collect reviewed product KPIs using the existing shared contracts.

## Intentionally blocked authority

Implemented diagnosis and verification layers do not authorize mutation. The following remain blocked:

- broad automatic patch application;
- automatic merge authorization;
- hosted service or cloud infrastructure without proven local demand.

A `safe_fix_candidate` value is eligibility evidence only. It is not patch, merge, publication, security-dismissal, or semantic-equivalence authority.

## Do not repeat completed work

- FailureVector extraction and artifact contracts are established.
- SafetyGate policy is established.
- Trajectory and repository memory are established.
- Replayable benchmark and verifier layers are established.
- PR reporting and file-backed local worker orchestration are established.
- Dependency resolver classification and unknown-wrapper first-failure extraction are covered.

New PRs should extend current adoption or evidence gaps rather than recreate these components under new names.

## Exact-failure evidence quality and remediation eligibility

The PR Quality check-intelligence path emits one canonical `first_failure` object. Its `evidence_quality` block is reporting-only and contains:

- `confidence`: `high`, `medium`, or `low`;
- `source`: the structured evidence source used to select the failure;
- `actionable`: whether the evidence identifies a concrete operator starting point;
- `uncertainty`: bounded reasons the evidence must remain review-first.

Safe-remediation eligibility consumes that same object. Formatting-only evidence is a candidate only when the exact failure is high-confidence, actionable, has no unresolved uncertainty, and references approved repository-owned paths. Candidate status never means that automation, immediate auto-fix, patch application, merge, security dismissal, publication, or semantic equivalence is authorized.
