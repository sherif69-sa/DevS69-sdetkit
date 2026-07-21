# Reviewed KPI portfolio report

Use this report when a maintainer needs one review-first view of the Product Maturity Radar and the verified real-repository KPI baseline.

The report is a projection over existing source artifacts. It does not replace the Product Maturity Radar, the reviewed KPI report, the capability matrix, or human review.

## Required source artifacts

```text
build/sdetkit/product-maturity-radar.json
build/sdetkit/adoption-product-kpi-report.json
build/formatter-policy-proposal-observation/formatter-policy-proposal-observation.json
docs/contracts/platform-capability-matrix.v1.json
docs/roadmap/product-roadmap.md
docs/operator-reviewed-kpi-portfolio-report.md
```

All sources must be readable, schema-compatible, bound to the current Git head, and carry valid deterministic provenance. A stale, malformed, authority-expanding, or foreign-head source blocks the portfolio projection.

## Generate the report

```bash
python -m sdetkit.product_maturity_radar_portfolio \
  --root . \
  --radar-json build/sdetkit/product-maturity-radar.json \
  --kpi-report-json build/sdetkit/adoption-product-kpi-report.json \
  --proposal-observation-report-json build/formatter-policy-proposal-observation/formatter-policy-proposal-observation.json \
  --out build/sdetkit/product-maturity-radar-portfolio.json \
  --format text
```

The command writes:

```text
build/sdetkit/product-maturity-radar-portfolio.json
build/sdetkit/product-maturity-radar-portfolio.md
```

## Verify freshness

```bash
python -m sdetkit.product_maturity_radar_portfolio \
  --root . \
  --radar-json build/sdetkit/product-maturity-radar.json \
  --kpi-report-json build/sdetkit/adoption-product-kpi-report.json \
  --proposal-observation-report-json build/formatter-policy-proposal-observation/formatter-policy-proposal-observation.json \
  --out build/sdetkit/product-maturity-radar-portfolio.json \
  --check-freshness \
  --format text
```

Freshness also binds the formatter proposal observation report to the current Git head.

## Read these fields first

```text
report_status
portfolio_status
current_head_sha
radar_projection
reviewed_kpi_evidence
formatter_policy_proposal_observation
capability_matrix
portfolio_documentation
operator_summary
input_provenance
authority_boundary
```

Inside `reviewed_kpi_evidence`, inspect:

```text
reviewed_observation_count
measured_metric_count
unavailable_metric_count
metrics_without_applicable_denominator
metrics
outcome_totals
```

The current baseline contains two reviewed observations, seven measured metrics, and zero unavailable metrics. Its reviewed outcomes total:

```text
pass=11
fail=0
unavailable=0
malformed=0
unsupported=0
not_applicable=3
```

All seven metrics now have applicable reviewed denominators. The three `not_applicable` outcomes remain visible because a reviewed observation may legitimately not exercise every metric; they are not converted into passes, failures, or authoritative zeroes.

## Formatter proposal observation

The repository-owned source currently contains zero reviewed proposal records. The fresh report therefore requires one real digest-bound review and keeps `false_authority_count=0`. Synthetic fixtures are not accepted as product evidence.

## Decision rule

Use measured reviewed metrics only. Do not infer unavailable outcomes, treat predictions as proof, or generalize one reviewed repository into a broad product-maturity claim.

The operator summary separates evidence continuity from the active implementation lane:

- `evidence_next_action` continues reviewed observation collection before broader product claims;
- `roadmap_next_slice` identifies the next review-first implementation lane: `formatter_policy_proposal_reviewed_evidence`.

Neither next action authorizes patch application, SafetyGate mutation, branch execution, target-repository execution, merge, publication, security dismissal, or semantic-equivalence claims.

## Authority boundary

Every field remains denied:

```text
automation_allowed=false
patch_application_allowed=false
publication_authorized=false
security_dismissal_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

The report is local, deterministic, reporting-only, projection-only, and review-first. It does not read or mutate a target repository, run target proof commands, publish a release, dismiss security findings, apply a patch, or authorize merge.
