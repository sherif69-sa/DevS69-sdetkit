# ICP Scoring Matrix (Execution Step 1)

## Purpose

This document operationalizes the founder brief into a practical ICP qualification system that can be used by product, founder-led sales, and partnerships.

Primary positioning anchor:
- SDETKit is the release-confidence layer for deterministic SHIP / NO-SHIP decisions with machine-readable evidence.

This ICP matrix turns that positioning into a repeatable process for deciding where to invest GTM effort.

---

## How to use this matrix

- Score every target account/opportunity on the 10 dimensions below.
- Each dimension is scored 0-10.
- Apply weighting to generate weighted total score out of 100.
- Use score band decisioning:
  - 80-100: Tier A (high-priority active pursuit)
  - 65-79: Tier B (qualified nurture / pilot)
  - 50-64: Tier C (light-touch / monitor)
  - <50: Tier D (deprioritize for now)

---

## ICP dimensions and weights

| # | Dimension | Weight | Why it matters |
|---|---|---:|---|
| 1 | Release risk exposure | 14 | Higher release risk increases urgency for deterministic release confidence. |
| 2 | Governance/compliance pressure | 12 | Governance-heavy teams value auditable artifacts and policy evidence. |
| 3 | CI standardization need | 10 | Teams with fragmented CI gain value from one canonical release path. |
| 4 | Multi-repo operational complexity | 10 | Complexity amplifies triage and decision inconsistency pain. |
| 5 | Failure triage pain | 10 | Slow triage directly maps to SDETKit’s artifact-first remediation value. |
| 6 | QA/SDET/platform maturity | 10 | Mature teams adopt process tools faster and expand usage. |
| 7 | Internal champion strength | 9 | A strong champion drives implementation speed and change management. |
| 8 | Tooling integration readiness | 8 | Readiness affects onboarding friction and time-to-value. |
| 9 | Budget authority & timing | 9 | Buying power and cycle timing determine deal velocity. |
| 10 | Strategic urgency (next 90 days) | 8 | Active initiatives create near-term adoption windows. |

Total weight = 100.

---

## Dimension scoring definitions

## 1) Release risk exposure (weight 14)

| Score | Qualification signal |
|---:|---|
| 0-2 | Low-risk internal tooling; outages rarely matter. |
| 3-4 | Moderate service impact; release issues manageable manually. |
| 5-6 | Noticeable production risk; post-release surprises happen monthly. |
| 7-8 | High impact incidents tied to release quality are frequent. |
| 9-10 | Mission-critical releases with high blast radius and executive attention. |

### Discovery prompts
- “How costly is a failed release in customer, SLA, or revenue terms?”
- “How often do release rollbacks occur?”
- “What percentage of incidents are linked to release changes?”

## 2) Governance/compliance pressure (weight 12)

| Score | Qualification signal |
|---:|---|
| 0-2 | No formal release controls; low audit needs. |
| 3-4 | Minimal compliance; occasional checklists. |
| 5-6 | Standard controls with periodic reviews. |
| 7-8 | Frequent audit requirements; evidence retention expected. |
| 9-10 | Strict regulated controls requiring machine-readable approval evidence. |

### Discovery prompts
- “What audit evidence do release approvers require today?”
- “Are release approvals linked to formal policy frameworks?”
- “How often do teams struggle to produce decision evidence?”

## 3) CI standardization need (weight 10)

| Score | Qualification signal |
|---:|---|
| 0-2 | Uniform CI across all repos; low process drift. |
| 3-4 | Minor variation but broadly standardized. |
| 5-6 | Several pipelines with non-trivial variation. |
| 7-8 | Significant inconsistency in release checks and outputs. |
| 9-10 | Fragmented CI causing chronic confidence and ownership gaps. |

### Discovery prompts
- “How many CI patterns are currently used across repos?”
- “Do teams produce comparable release decision artifacts?”
- “How often does CI disagreement block release decisions?”

## 4) Multi-repo operational complexity (weight 10)

| Score | Qualification signal |
|---:|---|
| 0-2 | Single repo, low integration load. |
| 3-4 | Few repos with light dependency graph. |
| 5-6 | Moderate repo estate with occasional coordination friction. |
| 7-8 | Large repo estate with frequent cross-team dependencies. |
| 9-10 | Portfolio-level complexity with ongoing aggregation/reporting pain. |

### Discovery prompts
- “How many active repositories are in release scope?”
- “How do you aggregate release confidence across repos?”
- “What is the escalation path for cross-repo release blockers?”

## 5) Failure triage pain (weight 10)

| Score | Qualification signal |
|---:|---|
| 0-2 | Fast triage, clear ownership, low friction. |
| 3-4 | Occasional triage delays. |
| 5-6 | Repeated delays due to scattered outputs. |
| 7-8 | Triage frequently stalls due to ambiguity and noisy logs. |
| 9-10 | Chronic triage bottlenecks with measurable engineering drag. |

### Discovery prompts
- “Mean time to triage first failure?”
- “How often do teams debate interpretation vs act on artifacts?”
- “Which failure classes consume the most coordination time?”

## 6) QA/SDET/platform maturity (weight 10)

| Score | Qualification signal |
|---:|---|
| 0-2 | Minimal quality engineering process. |
| 3-4 | Informal testing/quality workflows. |
| 5-6 | Defined quality practices but inconsistent enforcement. |
| 7-8 | Mature quality/reliability functions with clear ownership. |
| 9-10 | Advanced platform quality programs with executive visibility. |

### Discovery prompts
- “Who owns release quality policy today?”
- “Are quality KPIs reviewed weekly/monthly?”
- “How standardized are remediation workflows?”

## 7) Internal champion strength (weight 9)

| Score | Qualification signal |
|---:|---|
| 0-2 | No active sponsor, unclear ownership. |
| 3-4 | Interested individual contributor without influence. |
| 5-6 | Mid-level champion can run pilot but limited authority. |
| 7-8 | Senior technical owner with cross-team influence. |
| 9-10 | Executive-backed champion with mandate and urgency. |

### Discovery prompts
- “Who is accountable for release confidence outcomes?”
- “Can the champion secure pilot resources quickly?”
- “How far can this person push standardization?”

## 8) Tooling integration readiness (weight 8)

| Score | Qualification signal |
|---:|---|
| 0-2 | Tooling constraints block integrations. |
| 3-4 | Limited engineering bandwidth for implementation. |
| 5-6 | Moderate readiness but competing priorities. |
| 7-8 | Active reliability roadmap with implementation capacity. |
| 9-10 | Dedicated platform capacity and integration enablement. |

### Discovery prompts
- “Who can own technical onboarding in first 2 weeks?”
- “Any blockers for Python/CLI rollout?”
- “Can CI pipeline templates be updated this quarter?”

## 9) Budget authority & timing (weight 9)

| Score | Qualification signal |
|---:|---|
| 0-2 | No budget visibility; no sponsor path. |
| 3-4 | Budget uncertain; long-cycle discovery only. |
| 5-6 | Budget possible with pilot proof. |
| 7-8 | Budget owner involved, timing this/next quarter. |
| 9-10 | Budget approved or pre-allocated for release governance improvements. |

### Discovery prompts
- “Who signs budget for developer tooling/reliability?”
- “Is there funding this quarter for release confidence initiatives?”
- “What proof is required for procurement?”

## 10) Strategic urgency (next 90 days) (weight 8)

| Score | Qualification signal |
|---:|---|
| 0-2 | No near-term urgency. |
| 3-4 | Interest but no committed timeline. |
| 5-6 | Problem acknowledged with tentative quarter plan. |
| 7-8 | Active initiative underway with clear timeline. |
| 9-10 | Executive mandate or incident-driven urgency now. |

### Discovery prompts
- “What happens if this is not solved this quarter?”
- “Are there launch/release milestones at risk?”
- “Is leadership asking for measurable improvement now?”

---

## Scoring sheet template

Use this template per account:

| Dimension | Raw score (0-10) | Weight | Weighted score |
|---|---:|---:|---:|
| Release risk exposure |  | 14 |  |
| Governance/compliance pressure |  | 12 |  |
| CI standardization need |  | 10 |  |
| Multi-repo complexity |  | 10 |  |
| Failure triage pain |  | 10 |  |
| QA/SDET/platform maturity |  | 10 |  |
| Internal champion strength |  | 9 |  |
| Tooling integration readiness |  | 8 |  |
| Budget authority & timing |  | 9 |  |
| Strategic urgency |  | 8 |  |
| **Total** |  | **100** |  |

Formula:
- Weighted score = (Raw score / 10) × Weight

---

## Tiering rules and action playbook

### Tier A (80-100) — active pursuit

Actions:
1. Book 60-minute deep discovery.
2. Run first-proof pilot within 7 days.
3. Capture before/after triage metrics baseline.
4. Build proposal with ROI framing.

Expected cycle:
- 2-6 weeks to pilot outcome.

### Tier B (65-79) — qualified nurture / pilot shortlist

Actions:
1. 30-minute qualification + scoped pilot proposal.
2. Share role-based quickstart and fit narrative.
3. Re-score after 2 weeks based on urgency/champion updates.

Expected cycle:
- 4-10 weeks.

### Tier C (50-64) — monitor and educate

Actions:
1. Lightweight educational sequence.
2. Invite to workshop/webinar/office hours.
3. Trigger re-qualification on incident or governance event.

Expected cycle:
- 8-20+ weeks.

### Tier D (<50) — deprioritize

Actions:
1. Capture in CRM with next review date.
2. No proactive high-touch sales motion.
3. Revisit only when strategic trigger occurs.

---

## ICP hypothesis board (v1)

### Hypothesis H1
- Enterprises with strict release governance will convert faster because machine-readable artifacts reduce approval ambiguity.

Validation signal:
- Shorter pilot-to-expansion cycle in compliance-heavy teams.

### Hypothesis H2
- Platform teams managing 20+ repos will show the strongest ROI due to CI standardization and triage savings.

Validation signal:
- Improvement in first-failure triage and reduced release gate conflict.

### Hypothesis H3
- Teams with an executive-backed champion will expand from core gate path to enterprise workflows faster.

Validation signal:
- Higher 30-day activation + higher 90-day expansion rate.

---

## Discovery call script (structured)

### Opening (5 min)
- Confirm release confidence objective.
- Confirm desired outcomes in 30/60/90 days.

### Current-state mapping (10 min)
- Release flow today.
- Decision bottlenecks.
- Failure triage pattern.

### Pain quantification (10 min)
- Incident impact.
- Triage delay cost.
- Governance evidence friction.

### Future-state fit (10 min)
- Canonical gate path fit.
- Artifact workflow fit.
- CI rollout feasibility.

### Pilot design (10 min)
- Scope, timeline, owner.
- Baseline metrics.
- Success criteria.

### Close (5 min)
- Score account.
- Tier decision.
- Next-step commitment.

---

## Qualification anti-patterns

Avoid false positives:
1. “Interested” but no owner.
2. “Important” but no timeline.
3. “Need governance” but no approval process.
4. “Tooling initiative” but zero implementation bandwidth.

If 2 or more anti-patterns present, cap at Tier C until evidence changes.

---

## Evidence package required per qualified account

For Tier A/B opportunities, collect:
1. Current release process map.
2. Current failure triage process and latency estimate.
3. CI landscape summary.
4. Governance evidence requirements.
5. Named champion + decision chain.

---

## ROI baseline worksheet (input template)

| Metric | Baseline value | Target value | Time horizon |
|---|---:|---:|---|
| Mean time to triage first failure |  |  | 30 days |
| Failed release gate frequency |  |  | 30-90 days |
| Evidence completeness for approvals |  |  | 30 days |
| CI decision consistency |  |  | 30-90 days |

---

## Weekly operating rhythm for ICP execution

### Monday
- Re-score pipeline and prioritize Tier A work.

### Tuesday
- Run high-priority discovery and pilot scoping.

### Wednesday
- Build account-specific business cases.

### Thursday
- Execute technical pilot follow-up.

### Friday
- Review conversions, losses, and scoring calibration.

---

## Governance and ownership

- Owner: Founder/GM or Head of GTM.
- Contributors: Product, Solutions Engineer, Platform advocate.
- Review cadence: Weekly pipeline review + monthly scoring recalibration.

---

## Calibration guide (first 8 weeks)

Week 1-2:
- Run matrix on 20 historical prospects.

Week 3-4:
- Compare predicted tier vs actual engagement.

Week 5-6:
- Adjust weights if overfitting to one segment.

Week 7-8:
- Freeze v1.1 scoring model for quarter execution.

---

## Implementation notes

- Store scores in CRM with timestamp and owner.
- Keep free-text evidence notes per dimension.
- Maintain audit trail for score changes.

---

## Done criteria for this document

This ICP matrix is “done for v1” when:
1. All pipeline targets are scored.
2. Tiering drives weekly execution priorities.
3. Conversion data feeds monthly calibration.
