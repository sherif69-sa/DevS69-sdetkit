# Remediation research contract

The remediation-research contract is a deterministic, local-first evidence boundary for evaluating one reversible, PR-owned mechanical remediation family. It validates retained evidence and produces a review report. It does not apply patches, mutate a target repository, change SafetyGate policy, merge, publish, dismiss security findings, or prove semantic equivalence.

Machine-readable contract: [`contracts/remediation-research.v1.json`](contracts/remediation-research.v1.json).

## Schemas

```text
contract: sdetkit.remediation_research_contract.v1
evidence: sdetkit.remediation_research_evidence.v1
report:   sdetkit.remediation_research_report.v1
```

The first allowlisted candidate family is `formatter_only`. Adding another family requires a separate reviewed contract change.

## Required evidence

Each evidence object must contain:

- the candidate family and exact lower-snake-case failure class;
- source repository, source commit, and PR number;
- the exact PR-owned file scope;
- before and after inventories with SHA-256 and byte size;
- a retained proposed diff and the files it claims to modify;
- focused and full proof commands plus retained artifacts;
- an exact-byte rollback record;
- a reviewer identity, timestamp, decision, and notes;
- an explicit false-authority count;
- known limitations;
- every required scenario record.

Inventories and proposed-diff file lists must exactly match `pr_owned_scope`. Absolute paths, parent traversal, placeholders, missing digests, and unsupported scenarios are structural validation errors.

## Required scenarios

| Scenario | Required outcome | Meaning |
| --- | --- | --- |
| `no_op` | `pass` | Already-correct input produces no unauthorized change. |
| `oracle` | `pass` | Candidate output matches retained expected bytes. |
| `unsafe_patch` | `blocked` | Test weakening or another unsafe change is rejected. |
| `out_of_scope` | `blocked` | Writes outside the PR-owned scope are rejected. |
| `ambiguous` | `blocked` | Unclear ownership or intent remains review-first. |
| `rollback` | `pass` | Exact original bytes and inventory are restored. |

A structurally valid report can still be `review_required`. Readiness remains blocked when focused or full proof did not pass, rollback is unverified, the reviewer did not accept, the false-authority count is nonzero, or a scenario outcome differs from the contract.

## Local command

```bash
python -m sdetkit.remediation_research_contract \
  build/remediation/remediation-research-evidence.json \
  --contract-json docs/contracts/remediation-research.v1.json \
  --out-json build/remediation/remediation-research-report.json \
  --out-md build/remediation/remediation-research-report.md \
  --format json
```

The command reads local JSON, normalizes it deterministically, binds the report to SHA-256 digests of the contract, evidence, and generator, and writes optional JSON and Markdown reports. It runs no candidate commands and performs no target-repository mutation.

## Report states

- `review_ready`: the evidence is structurally valid and the recorded proof, rollback, reviewer, false-authority, and scenario outcomes meet the contract.
- `review_required`: evidence is incomplete, structurally invalid, or not yet acceptable for human benchmark review.

`review_ready` is not promotion or execution authority. It only means the evidence packet is complete enough for the next human-reviewed benchmark decision.

## Authority boundary

```text
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
publication_authorized=false
security_dismissal_allowed=false
semantic_equivalence_proven=false
```

History, benchmark results, and reviewer records remain advisory evidence. A later PR must independently prove verifier, trajectory, rollback, and false-authority behavior before any narrow policy promotion is considered.
