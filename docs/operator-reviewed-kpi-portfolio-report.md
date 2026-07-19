# Reviewed KPI portfolio report

Use this report when a maintainer needs one review-first view of the Product Maturity Radar and the verified real-repository KPI baseline.

The report is a projection over existing source artifacts. It does not replace the Product Maturity Radar, the reviewed KPI report, the capability matrix, or human review.

## Required source artifacts

```text
build/sdetkit/product-maturity-radar.json
build/sdetkit/adoption-product-kpi-report.json
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
  --out build/sdetkit/product-maturity-radar-portfolio.json \
  --check-freshness \
  --format text
```

Freshness binds the output to the exact bytes of the radar, KPI report, capability matrix, roadmap, operator guide, generator, and current Git head.

## Read these fields first

```text
report_status
portfolio_status
current_head_sha
radar_projection
reviewed_kpi_evidence
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

The first baseline contains one reviewed observation, five measured metrics, and two unavailable metrics:

```text
first_failure_extraction_precision
workspace_ownership_precision
```

Those two metrics retain `precision=null` because this observation did not exercise a failing CI log or a mixed-workspace ownership decision. They are not converted into passes or authoritative zeroes.

## Decision rule

Use measured reviewed metrics only. Do not infer unavailable outcomes, treat predictions as proof, or generalize one reviewed repository into a broad product-maturity claim.

The operator summary separates two next actions:

- `evidence_next_action` identifies which reviewed denominators still need observations;
- `roadmap_next_slice` identifies the next implementation lane, currently conservative Azure DevOps proof discovery.

Neither next action authorizes code changes or target-repository execution.

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
