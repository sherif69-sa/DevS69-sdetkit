# Reviewed real-repository product KPI evidence

Contract: [`docs/contracts/adoption-product-kpi-evidence.v1.json`](contracts/adoption-product-kpi-evidence.v1.json)

## Purpose

This lane measures how well SDETKit discovers, diagnoses, scopes, and explains real repository evidence. It replaces anecdotal maturity claims with reviewed observations and explicit denominators.

The contract is intentionally report-only. It does not authorize target-repository execution, mutation, patch application, merge, publication, security dismissal, or semantic-equivalence claims.

## Required reviewed metrics

| Metric | Review question |
| --- | --- |
| Discovery precision | Did SDETKit identify the repository surface correctly from retained evidence? |
| First-failure extraction precision | Did it identify the first meaningful failure beneath wrapper noise? |
| Workspace ownership precision | Did it map the evidence to the correct workspace or owner surface? |
| Proof-command actionability | Was the recommendation concrete, scoped, and runnable by a trusted operator? |
| Authority-boundary preservation | Did the output remain review-first and non-authorizing? |
| Unsafe-authority rejection | Did it reject mutation, merge, publication, dismissal, or unproven equivalence authority? |
| Operator actionability | Did a reviewer receive one clear next human action without an overstated success claim? |

## Observation evidence

Every reviewed observation must retain:

```text
observation_id
repository_name
repository_url
source_commit_sha
evidence_path
evidence_sha256
reviewer_id
reviewed_at
metric_outcomes
review_notes
```

An outcome is one of:

```text
pass
fail
unavailable
malformed
unsupported
not_applicable
```

Unavailable, malformed, and unsupported evidence remains visible. The reporter must not convert a collection failure into an authoritative zero, infer a missing review result, or silently remove difficult observations from the denominator.

## Denominator rule

Each KPI reports its reviewed pass count and reviewed applicable denominator together with the complete outcome totals. A percentage without the source count, review state, and provenance is not product proof.

## What this contract proves

The contract proves the expected shape and safety boundary for a future deterministic KPI evaluator. It does not yet prove real-repository product performance. That proof requires reviewed observation records, source provenance, a generated report, freshness validation, and repository CI.

## Planned implementation sequence

1. Versioned contract and tests.
2. Deterministic JSON and Markdown evaluator.
3. Reviewed real-repository observation set with explicit denominators.
4. Capability-matrix, maturity-radar, roadmap, and operator-report integration.

The sequence remains local-first and review-first. No hosted service or patch execution is required for this lane.
