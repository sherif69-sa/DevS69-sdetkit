# Pricing Logic v1 (Execution Step 2)

## Objective

Translate product value into a pricing model that scales with customer risk exposure, governance needs, and operational complexity.

Positioning anchor:
- Deterministic release decisions + evidence-backed governance + reduced triage overhead.

---

## Pricing principles

1. Price by measurable business value, not command count.
2. Keep entry friction low for bottom-up adoption.
3. Make enterprise governance value explicit and premium.
4. Preserve a strong OSS core to accelerate credibility and trust.
5. Align monetization with customer maturity journey.

---

## Package architecture

## Tier 0 — OSS Core (Free)

### Intended buyer/user
- Individual devs, small teams, exploratory adopters.

### Included value
- Canonical gate path support.
- Basic artifact generation and interpretation patterns.
- Community docs and community support paths.

### Business role
- Top-of-funnel engine.
- Standardized language for release-confidence category creation.

### Conversion trigger to paid
- Need for multi-repo governance.
- Need for deeper reporting/automation.
- Need for policy/compliance guardrails.

---

## Tier 1 — Team / Pro

### Intended buyer/user
- Engineering managers, QA leads, platform team leads.

### Value scope
- Team-level governance overlays.
- Enhanced reporting and trend views.
- Better workflow templates and operational guardrails.
- Faster issue-to-remediation loops.

### Packaging candidates
- Policy profile templates.
- Artifact rollup packs.
- Team SLA support (business hours).

### Pricing unit options (evaluate)
- Per active repository (recommended for simplicity).
- Per engineering seat (secondary option).
- Hybrid base + repo blocks (good for mid-market).

### Recommendation
- Start with per-repository pricing for clearer value mapping.

---

## Tier 2 — Enterprise

### Intended buyer/user
- VP Engineering, Head of Platform, Release Governance leaders.

### Value scope
- Portfolio-level release confidence rollups.
- Governance and audit-grade evidence workflows.
- Enterprise reliability routines and escalation management.
- Advanced support, onboarding, and change enablement.

### Packaging candidates
- Portfolio dashboards.
- Policy packs by regulatory posture.
- Executive reliability scorecards.
- Premium support + architecture advisory.

### Pricing unit options
- Annual platform license with repo bands.
- Add-on for regulated/compliance bundle.
- Premium support and onboarding add-on.

### Recommendation
- Use annual contract with tiered repo bands + support package.

---

## Candidate pricing structure (illustrative)

> Note: Numerical values below are placeholders for model testing and should be validated in customer conversations.

## Team / Pro (monthly)
- Band A: 1-10 repos
- Band B: 11-30 repos
- Band C: 31-75 repos
- Band D: 76+ repos

## Enterprise (annual)
- Base platform fee + repo band multiplier
- Optional add-ons:
  - Compliance evidence bundle
  - White-glove onboarding
  - Premium support SLA

---

## Value metric selection framework

Evaluate each metric against:
1. Customer-perceived fairness
2. Predictability for buyer budgeting
3. Expansion alignment
4. Sales simplicity
5. Instrumentation ease

Score each 1-5.

| Metric | Fairness | Predictability | Expansion fit | Sales simplicity | Instrumentation | Total |
|---|---:|---:|---:|---:|---:|---:|
| Active repositories | 5 | 5 | 5 | 4 | 5 | 24 |
| Engineering seats | 3 | 4 | 3 | 4 | 3 | 17 |
| Pipeline runs | 2 | 2 | 3 | 2 | 4 | 13 |
| Hybrid (base + repos) | 4 | 4 | 5 | 3 | 4 | 20 |

Recommendation: start with **active repositories**.

---

## Monetization journey map

### Stage 1: Land
- User installs and runs canonical first proof.
- Sees deterministic ship/no-ship output and useful artifacts.

### Stage 2: Validate
- Team deploys in one repo/pipeline.
- Measures triage and confidence improvements.

### Stage 3: Expand
- Standardize across additional repos.
- Introduce governance and policy controls.

### Stage 4: Institutionalize
- Portfolio reporting and executive dashboards.
- Formal reliability and compliance cadence.

---

## Conversion trigger matrix

| Trigger | Signal | Sales action |
|---|---|---|
| Repeated NO-SHIP runs | High release friction and remediation urgency | Offer Team pilot with remediation coaching |
| Governance audit pain | Evidence demands increasing | Position enterprise evidence bundle |
| CI inconsistency across repos | Fragmented release decisions | Position multi-repo standardization plan |
| High triage latency | Slow issue ownership and diagnosis | Position artifact-led triage workflows |

---

## Packaging by persona

## Persona: Platform lead
- Concern: consistency and scale.
- Offer: multi-repo governance + rollups.

## Persona: QA/SDET lead
- Concern: confidence and reproducibility.
- Offer: deterministic gates + quality evidence workflows.

## Persona: Engineering manager
- Concern: release velocity and predictability.
- Offer: team-level decision consistency + lower triage time.

## Persona: Compliance/security stakeholder
- Concern: auditable decision trace.
- Offer: contract-driven evidence artifacts and retention policies.

---

## Commercial motion by segment

## SMB / small-mid teams
- Motion: self-serve + assisted onboarding.
- Sales cycle: short.
- Pricing: simple monthly repo bands.

## Mid-market
- Motion: founder-led + solutions support.
- Sales cycle: medium.
- Pricing: annual with expansion checkpoints.

## Enterprise
- Motion: consultative + pilot + procurement.
- Sales cycle: long.
- Pricing: annual platform with governance add-ons.

---

## Discounting guardrails

1. No discount without explicit success plan.
2. Tie discount to term length and scope commitment.
3. Avoid deep discounts that anchor low willingness to pay.
4. Prefer value-add credits over pure price reductions.

---

## Pilot pricing logic

Pilot objective:
- Prove measurable value quickly and de-risk larger commitment.

Pilot design options:
1. Paid pilot with credit toward annual.
2. Low-cost fixed-scope pilot (2-4 weeks).
3. Sponsored design partner motion (strict criteria only).

Pilot success metrics:
- Reduced triage time.
- Improved release decision consistency.
- Improved governance evidence quality.

---

## Expansion playbook

Post-pilot expansion triggers:
1. Positive KPI movement in first 30 days.
2. Champion requests broader rollout.
3. Leadership asks for portfolio-level visibility.

Expansion sequencing:
- Repo 1-3 standardization.
- Repo 4-15 process normalization.
- Repo 16+ governance and portfolio control loops.

---

## Renewal logic

Renewals should be framed around:
1. Reliability delta delivered.
2. Risk reduction outcomes.
3. Organizational standardization progress.
4. Governance maturity and audit readiness.

Renewal package:
- Outcome report
- Year-over-year KPI shifts
- Next-phase roadmap

---

## KPI model for pricing validation

Track these pricing-performance KPIs monthly:
1. Free-to-paid conversion rate.
2. Time from first proof to paid pilot.
3. Pilot-to-paid conversion rate.
4. Net revenue retention by segment.
5. Expansion ARR from repo growth.

---

## Objection handling library (pricing)

### “We can script this ourselves.”
Response:
- DIY scripts handle command execution, but not stable decision contracts, governance narrative, and reusable evidence models.

### “We already have CI checks.”
Response:
- Existing checks are often fragmented; SDETKit standardizes decision interpretation and evidence portability.

### “Budget is tight.”
Response:
- Start with narrow pilot tied to triage-time and release-risk reduction targets.

### “We only need this for one repo.”
Response:
- Begin with one repo; pricing and rollout are designed for staged expansion.

---

## Pricing experiments backlog (first 90 days)

Experiment 1:
- Compare repo-based vs hybrid pricing proposal acceptance.

Experiment 2:
- Compare paid pilot vs low-cost pilot conversion quality.

Experiment 3:
- Compare annual prepay incentive vs onboarding-credit incentive.

Experiment 4:
- Test support SLA add-on demand in enterprise pilots.

---

## Governance and ownership

- Owner: Founder / Head of Revenue.
- Inputs: Product, Solutions Engineering, Customer Success.
- Review cadence: bi-weekly pricing council.

---

## Decision log template

For every deal, log:
- Segment
- Package offered
- Discount details
- Objections
- Win/loss outcome
- Lessons for model revision

---

## Price change policy

1. Batch pricing updates quarterly.
2. Preserve grandfathering rules for active annual customers.
3. Communicate value improvements before price increases.
4. Provide migration paths for legacy plans.

---

## Done criteria for Pricing v1

Pricing v1 is considered ready when:
1. Package architecture is approved.
2. Value metric is selected and instrumented.
3. Pilot terms are standardized.
4. Objection library and discount guardrails are adopted by sales.
