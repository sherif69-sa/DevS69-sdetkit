# Reviewed real-repository product KPI evidence

Contract: [`docs/contracts/adoption-product-kpi-evidence.v1.json`](contracts/adoption-product-kpi-evidence.v1.json)

## Purpose

This lane measures how well SDETKit discovers, diagnoses, scopes, and explains real repository evidence. It replaces anecdotal maturity claims with reviewed observations and explicit denominators.

The evaluator is intentionally report-only. It does not authorize target-repository execution, mutation, patch application, merge, publication, security dismissal, or semantic-equivalence claims.

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

Unavailable, malformed, and unsupported evidence remains visible. The evaluator does not convert a collection failure into an authoritative zero, infer a missing review result, or silently remove difficult observations from the report.

## Observation input

The evaluator accepts one JSON object using schema `sdetkit.adoption_product_kpi_observations.v1`:

```json
{
  "schema_version": "sdetkit.adoption_product_kpi_observations.v1",
  "observations": [
    {
      "observation_id": "repo-001",
      "repository_name": "example-repo",
      "repository_url": "https://example.invalid/example-repo",
      "source_commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "evidence_path": "evidence/repo-001.json",
      "evidence_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "reviewer_id": "reviewer-1",
      "reviewed_at": "2026-07-18T12:00:00Z",
      "metric_outcomes": {
        "discovery_precision": "pass",
        "first_failure_extraction_precision": "pass",
        "workspace_ownership_precision": "pass",
        "proof_command_actionability": "pass",
        "authority_boundary_preservation": "pass",
        "unsafe_authority_rejection": "pass",
        "operator_actionability": "pass"
      },
      "review_notes": "Reviewed against retained source evidence."
    }
  ]
}
```

Every contracted metric is required for every observation. Reviewer timestamps must include a timezone, source commits must be hexadecimal, and retained evidence must carry its SHA-256 digest.

## Generate the report

```bash
python -m sdetkit.adoption_product_kpi_report \
  --observations-json build/sdetkit/reviewed-kpi-observations.json \
  --out build/sdetkit/adoption-product-kpi-report.json \
  --format text
```

The command writes both:

```text
build/sdetkit/adoption-product-kpi-report.json
build/sdetkit/adoption-product-kpi-report.md
```

The JSON artifact contains the reviewed observation count, metric totals, complete outcome counts, source relationships, input digest, current Git head, review provenance index, rules, and denied authority.

## Denominator rule

For each metric:

```text
numerator = pass
denominator = pass + fail
```

Unavailable, malformed, unsupported, and not-applicable outcomes remain visible beside the denominator. When `pass + fail` is zero, precision is `null` and status is `unavailable`; the evaluator never reports a fabricated `0%`.

## Freshness validation

```bash
python -m sdetkit.adoption_product_kpi_report \
  --observations-json build/sdetkit/reviewed-kpi-observations.json \
  --out build/sdetkit/adoption-product-kpi-report.json \
  --check-freshness \
  --format text
```

Freshness binds the report to:

- the exact observation bytes;
- the exact KPI contract bytes;
- the evaluator source;
- the accepted schema versions;
- the current repository head;
- the complete metric and authority payload.

A changed observation, contract, generator, head, metric count, authority value, or report body makes the artifact stale.

## What the evaluator proves

The evaluator proves that a report is a deterministic aggregation of the supplied reviewed records and that its source and authority boundaries have not drifted. It does not prove that the supplied human reviews are correct, that a target repository endorses SDETKit, or that a prediction is equivalent to retained evidence.

## Implementation sequence

1. Versioned contract and tests — complete.
2. Deterministic JSON and Markdown evaluator — implemented in this slice.
3. Reviewed real-repository observation set with explicit denominators — next.
4. Capability-matrix, maturity-radar, roadmap, and operator-report integration — after real evidence exists.

The sequence remains local-first and review-first. No hosted service or target-repository execution is required for this lane.
