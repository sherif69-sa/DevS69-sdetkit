# FailureVector support matrix

This page is the Wave A checkpoint for the FailureVectorEngine.

It records which failure classes are currently supported, how they should be treated, and what must not be repeated in later PRs.

Contract file:

- `docs/contracts/failure-vector-support-matrix.v1.json`

## Supported failure classes

| Failure class | Default risk | Safe-fix candidate | Review policy | First signal contract |
| --- | --- | --- | --- | --- |
| `test` | `medium` | `False` | `review_or_focused_proof` | pytest FAILED node id or assertion failure line |
| `formatter_only` | `low` | `True` | `mechanical_safe_fix_allowed_when_pr_owned` | ruff format failed or would be reformatted |
| `lint` | `medium` | `only mechanically fixable lint such as I001 import sorting` | `safe_fix_only_for_low_risk_mechanical_lint` | ruff rule line or ruff check signal |
| `type` | `medium` | `False` | `review_first` | mypy file:line error |
| `dependency` | `high` | `False` | `review_first` | pip resolver failure such as ResolutionImpossible |
| `merge_conflict` | `high` | `False` | `review_first` | CONFLICT line or merge conflict signal |
| `unknown` | `high` | `False` | `review_first` | first meaningful wrapper line, not generic exit-code fallback |

## Roadmap boundary

Wave A is about extraction and artifact evidence.

After this matrix is green:

1. Finish any missing FailureVector documentation/indexing only if it is directly related to this support matrix.
2. Move to Wave B: SafetyGate policy expansion.
3. Do not start TrajectoryStore, ReplayableBenchmarkHarness, ProtectedVerifier, PRReporter, JobQueue, cloud, service, or dashboard work until their roadmap waves are reached.

## Non-loop rule

Do not repeat completed work:

- dependency resolver classification is already covered.
- unknown wrapper first meaningful line extraction is already covered.
- CLI JSON/Markdown artifact coverage is already covered.
- workflow permission evidence lane is already complete.
