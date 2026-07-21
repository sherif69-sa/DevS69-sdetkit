# Formatter verifier and trajectory proof

This proof connects retained formatter-candidate benchmark evidence to the existing `ProtectedVerifier`, `TrajectoryStore`, `ReplayableBenchmarkHarness`, and `RepoMemory` contracts.

The proof is read-only and review-first. It validates evidence that already exists; it does not execute a formatter, apply a target patch, change SafetyGate policy, promote a remediation family, authorize merge, or prove semantic equivalence.

## Inputs

The command consumes the output directory created by the formatter candidate benchmark:

```text
formatter-candidate-benchmark.json
remediation-research-evidence.json
remediation-research-report.json
proposed.diff
focused-proof.json
full-proof.json
rollback.json
scenario-*.json
```

Every referenced artifact must be a normal file inside the benchmark directory. Symlinked, missing, shadowed, or digest-mismatched evidence is rejected.

## Verification contract

The verifier requires all of the following:

```text
benchmark_status=passed
research_contract_structurally_valid=true
claimed_scope_equals_diff_files=true
claimed_files_equal_actual_writes=true
all_six_scenarios_retained=true
non_oracle_scenarios_retain_no_writes=true
test_weakening_count=0
rollback_exact_bytes=true
proof_artifact_digests_match=true
false_authority_count=0
proof_inputs_unchanged=true
```

The existing compatibility verifier then checks exact changed-file inventory, allowed scope, captured proof commands, protected paths, and authority boundaries. Its successful state is:

```text
protected_verifier_status=structurally_verified_candidate
structural_verification_passed=true
semantic_equivalence_proven=false
```

Structural verification is not patch authority and is not semantic proof.

## Trajectory contract

The verifier writes one deterministic review-first trajectory record. The record retains:

- repository, branch, commit, and pull-request identity;
- formatter-only failure class and PR-owned source scope;
- captured proof commands;
- focused, quality, and verifier states;
- `review_first=true`;
- `auto_fix_allowed=false`;
- `final_result=review_required`;
- explicit denied authority fields.

The trajectory is evidence for later reviewed analysis. It does not authorize a future action.

## RepoMemory contract

The read-only RepoMemory profile records:

- a proven fixture benchmark contract;
- one recurring review-first formatting surface;
- zero known safe candidates;
- zero live safe candidates;
- one controlled candidate validation record;
- zero current-PR decision input;
- denied automation, merge, and semantic-equivalence authority.

RepoMemory stores observed proof and review context. It does not execute commands or promote policy.

## Local command

First create the benchmark packet:

```bash
python -m sdetkit.formatter_candidate_benchmark \
  --source-repository sherif69-sa/DevS69-sdetkit \
  --source-commit-sha "$(git rev-parse HEAD)" \
  --pr-number <pull-request-number> \
  --reviewer-id <reviewer-identity> \
  --reviewed-at <RFC3339-timestamp> \
  --reviewer-decision accept \
  --reviewer-notes "Accepted evidence for verifier contract review." \
  --contract-json docs/contracts/remediation-research.v1.json \
  --out-dir build/formatter-candidate-benchmark \
  --format json
```

Then verify and record the evidence:

```bash
python -m sdetkit.formatter_candidate_verifier \
  --benchmark-dir build/formatter-candidate-benchmark \
  --out-dir build/formatter-candidate-verifier \
  --repo sherif69-sa/DevS69-sdetkit \
  --branch "$(git branch --show-current)" \
  --commit-sha "$(git rev-parse HEAD)" \
  --pr-number <pull-request-number> \
  --reviewed-at <RFC3339-timestamp> \
  --format json
```

## Outputs

```text
formatter-candidate-verifier.json
formatter-candidate-verifier.md
protected-verifier-result.json
formatter-replay-report.json
formatter-trajectory.jsonl
formatter-repo-memory.json
formatter-controlled-validation.json
```

The output directory must be outside the benchmark evidence directory so verifier results cannot shadow or mutate proof inputs.

## Failure behavior

The command returns exit code `2` and writes no success claim when it finds:

- a missing or shadowed artifact;
- a digest mismatch;
- a scenario identity or expectation mismatch;
- retained writes outside the oracle scenario;
- test-surface writes;
- claimed scope that differs from the proposed diff or observed writes;
- failed exact-byte rollback;
- uncaptured or failed proof commands;
- authority expansion;
- input mutation during verification.

## Authority boundary

```text
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
publication_authorized=false
security_dismissal_allowed=false
semantic_equivalence_proven=false
```

This slice completes verifier and trajectory proof for the formatter candidate. Any policy promotion remains a separate authenticated, human-reviewed PR with its own scope, rollback, and authority contract.
