# Formatter candidate benchmark

The formatter candidate benchmark evaluates the first remediation-research family, `formatter_only`, through a disposable local fixture. It produces retained evidence for human review without applying a patch to the source repository or changing SafetyGate policy.

The benchmark is an evaluation surface, not an execution or promotion surface.

## What it proves

The benchmark records six required scenarios from the versioned remediation-research contract:

| Scenario | Required outcome | Benchmark behavior |
| --- | --- | --- |
| `no_op` | `pass` | Runs the formatter on already formatted input and confirms that no file changes. |
| `oracle` | `pass` | Formats an intentionally unformatted file, retains the exact diff, and confirms the result passes formatter validation. |
| `unsafe_patch` | `blocked` | Rejects a candidate that includes a test file before formatter execution. |
| `out_of_scope` | `blocked` | Rejects a candidate that claims a write outside the exact PR-owned file scope. |
| `ambiguous` | `blocked` | Keeps multiple possible owner files review-first. |
| `rollback` | `pass` | Restores the exact original bytes and verifies the complete fixture inventory. |

A successful benchmark also requires:

```text
out_of_scope_write_count=0
test_weakening_count=0
false_positive_count=0
rollback_verified=true
contract_structurally_valid=true
```

## Local command

Run the benchmark from a trusted development environment with the repository development dependencies installed:

```bash
python -m sdetkit.formatter_candidate_benchmark \
  --source-repository sherif69-sa/DevS69-sdetkit \
  --source-commit-sha "$(git rev-parse HEAD)" \
  --pr-number <pull-request-number> \
  --reviewer-id <reviewer-identity> \
  --reviewed-at <RFC3339-timestamp> \
  --reviewer-decision defer \
  --reviewer-notes "Evidence retained for human review; no promotion decision." \
  --contract-json docs/contracts/remediation-research.v1.json \
  --out-dir build/formatter-candidate-benchmark \
  --format json
```

Use `defer` until a human has reviewed the retained evidence. A benchmark may pass while the remediation-research report remains `review_required`; that is the expected review-first state.

## Retained artifacts

The default output directory is `build/formatter-candidate-benchmark/`.

```text
formatter-candidate-benchmark.json
formatter-candidate-benchmark.md
remediation-research-evidence.json
remediation-research-report.json
remediation-research-report.md
proposed.diff
focused-proof.json
full-proof.json
rollback.json
scenario-ambiguous.json
scenario-no_op.json
scenario-oracle.json
scenario-out_of_scope.json
scenario-rollback.json
scenario-unsafe_patch.json
```

The evidence packet includes exact before/after SHA-256 inventories, the proposed diff digest, focused and full fixture proof records, rollback evidence, all six scenario records, reviewer state, known limitations, and an explicit false-authority count.

## Isolation and scope

The benchmark creates temporary fixture workspaces and runs the pinned formatter only inside those workspaces. It does not accept a target-repository path and does not use the source repository as the formatter working directory.

The full proof in this slice is intentionally fixture-scoped. It proves formatter and lint behavior for the disposable benchmark repository; it does not claim that target-repository tests, semantic equivalence, or production behavior were executed.

## Authority boundary

```text
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
publication_authorized=false
security_dismissal_allowed=false
semantic_equivalence_proven=false
```

A `passed` benchmark means the formatter-only candidate met the research scenario contract. It does not promote the candidate, authorize branch mutation, or change any current SafetyGate decision.

## Next boundary

The next separate PR connects retained formatter-candidate evidence to `ProtectedVerifier`, `ReplayableBenchmarkHarness`, `TrajectoryStore`, and `RepoMemory`. That follow-up must prove claimed files equal actual writes, proof inputs are not mutated or shadowed, rollback restores exact bytes, and reviewed trajectories retain zero unsafe false-authority decisions.
