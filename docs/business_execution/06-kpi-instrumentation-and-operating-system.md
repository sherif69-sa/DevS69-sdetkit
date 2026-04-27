# KPI Instrumentation and Operating System (Execution Step 6)

## Purpose

Define a concrete measurement system for pipeline quality, pilot success, conversion efficiency, and expansion durability.

---

## Instrumentation principles

1. Every KPI must have a formula, owner, cadence, and threshold.
2. Every threshold breach must map to an action SLA.
3. Metric definitions are frozen per quarter to preserve comparability.
4. Weekly and monthly dashboards must include narrative interpretation, not only numbers.

---

## Core KPI catalog

| KPI | Definition | Cadence | Owner |
|---|---|---|---|
| `new_qualified_opps` | Count of Tier A/B accounts newly qualified this week | weekly | GTM lead |
| `discovery_completion_rate` | completed_discovery/booked_discovery | weekly | SDR/GTM |
| `discovery_to_pilot_rate` | pilot_starts/qualified_accounts | weekly | GTM lead |
| `pilot_to_paid_rate` | paid_conversions/completed_pilots | monthly | Founder |
| `time_to_first_value_days` | days from kickoff to first KPI improvement | weekly | Solutions lead |
| `mtttf` | mean time to triage first failure | weekly | Solutions/Platform |
| `failed_gate_frequency` | failed_gate_runs/total_gate_runs | weekly | Customer + Solutions |
| `expansion_rate` | expanded_accounts/paid_accounts | monthly | CS/GTM |
| `nrr` | (start_arr+expansion-churn)/start_arr | quarterly | Finance |
| `sales_cycle_days` | days discovery_to_close | monthly | GTM lead |
| `proposal_acceptance_rate` | accepted_proposals/sent_proposals | weekly | Founder/GTM |
| `pilot_scope_change_rate` | scope_changes/pilots | weekly | Solutions lead |

---

## KPI definition cards

### KPI card 1: `new_qualified_opps`

- Definition: Count of Tier A/B accounts newly qualified this week
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: weekly
- Owner: GTM lead
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: <8=red, 8-15=yellow, >15=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

### KPI card 2: `discovery_completion_rate`

- Definition: completed_discovery/booked_discovery
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: weekly
- Owner: SDR/GTM
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: <60%=red, 60-80%=yellow, >80%=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

### KPI card 3: `discovery_to_pilot_rate`

- Definition: pilot_starts/qualified_accounts
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: weekly
- Owner: GTM lead
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: <15%=red, 15-30%=yellow, >30%=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

### KPI card 4: `pilot_to_paid_rate`

- Definition: paid_conversions/completed_pilots
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: monthly
- Owner: Founder
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: <20%=red, 20-40%=yellow, >40%=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

### KPI card 5: `time_to_first_value_days`

- Definition: days from kickoff to first KPI improvement
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: weekly
- Owner: Solutions lead
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: >21=red, 14-21=yellow, <14=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

### KPI card 6: `mtttf`

- Definition: mean time to triage first failure
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: weekly
- Owner: Solutions/Platform
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: >48h=red, 24-48h=yellow, <24h=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

### KPI card 7: `failed_gate_frequency`

- Definition: failed_gate_runs/total_gate_runs
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: weekly
- Owner: Customer + Solutions
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: >30%=red, 15-30%=yellow, <15%=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

### KPI card 8: `expansion_rate`

- Definition: expanded_accounts/paid_accounts
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: monthly
- Owner: CS/GTM
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: <10%=red, 10-20%=yellow, >20%=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

### KPI card 9: `nrr`

- Definition: (start_arr+expansion-churn)/start_arr
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: quarterly
- Owner: Finance
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: <100%=red, 100-115%=yellow, >115%=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

### KPI card 10: `sales_cycle_days`

- Definition: days discovery_to_close
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: monthly
- Owner: GTM lead
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: >90=red, 60-90=yellow, <60=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

### KPI card 11: `proposal_acceptance_rate`

- Definition: accepted_proposals/sent_proposals
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: weekly
- Owner: Founder/GTM
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: <20%=red, 20-35%=yellow, >35%=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

### KPI card 12: `pilot_scope_change_rate`

- Definition: scope_changes/pilots
- Formula: documented in analytics dictionary and CRM computed fields.
- Cadence: weekly
- Owner: Solutions lead
- Source systems: CRM, pilot tracker, weekly operating memo, and dashboard store.
- Threshold bands: >30%=red, 15-30%=yellow, <15%=green
- Response playbook:
  - Red: root-cause review within 24h and corrective plan within 48h.
  - Yellow: monitor and adjust in weekly operating review.
  - Green: maintain with continuous optimization.
- Downstream decisions impacted:
  - ICP prioritization
  - pilot staffing
  - pricing/package positioning
  - forecast confidence

---

## Dashboard architecture

### Weekly execution dashboard
- Pipeline volume by stage and segment
- Discovery quality and progression
- Pilot health and blockers
- Proposal velocity and acceptance

### Monthly business dashboard
- Conversion cohorts and cycle time
- Pricing experiment performance
- Expansion and renewal movement
- Segment-level efficiency

### Quarterly strategy dashboard
- NRR and expansion durability
- Enterprise deal motion
- Moat scorecard and trust indicators

---

## Data quality controls

| Control | Rule | Owner | Escalation SLA |
|---|---|---|---|
| Completeness | 100% required fields for active opportunities | Ops analyst | 24h |
| Freshness | No active stage update older than 7 days | GTM ops | 48h |
| Consistency | CRM stage and dashboard stage must match | Ops analyst | 72h |
| Formula integrity | No KPI formula edits mid-quarter without approval | Founder + Ops | same day |

---

## Weekly operating review protocol

### Weekly protocol instance 1

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 2

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 3

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 4

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 5

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 6

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 7

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 8

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 9

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 10

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 11

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 12

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 13

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 14

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 15

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 16

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 17

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 18

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 19

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 20

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 21

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 22

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 23

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 24

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 25

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

### Weekly protocol instance 26

1. Review top 5 KPI movers.
2. Identify 3 root-cause hypotheses for red/yellow metrics.
3. Decide corrective actions with named owners and due dates.
4. Confirm forecast implications.
5. Publish operating memo and action tracker.

---

## Threshold breach runbooks

### Runbook 1: `new_qualified_opps` breach

- Trigger threshold: <8=red, 8-15=yellow, >15=green
- Incident owner: GTM lead
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

### Runbook 2: `discovery_completion_rate` breach

- Trigger threshold: <60%=red, 60-80%=yellow, >80%=green
- Incident owner: SDR/GTM
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

### Runbook 3: `discovery_to_pilot_rate` breach

- Trigger threshold: <15%=red, 15-30%=yellow, >30%=green
- Incident owner: GTM lead
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

### Runbook 4: `pilot_to_paid_rate` breach

- Trigger threshold: <20%=red, 20-40%=yellow, >40%=green
- Incident owner: Founder
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

### Runbook 5: `time_to_first_value_days` breach

- Trigger threshold: >21=red, 14-21=yellow, <14=green
- Incident owner: Solutions lead
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

### Runbook 6: `mtttf` breach

- Trigger threshold: >48h=red, 24-48h=yellow, <24h=green
- Incident owner: Solutions/Platform
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

### Runbook 7: `failed_gate_frequency` breach

- Trigger threshold: >30%=red, 15-30%=yellow, <15%=green
- Incident owner: Customer + Solutions
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

### Runbook 8: `expansion_rate` breach

- Trigger threshold: <10%=red, 10-20%=yellow, >20%=green
- Incident owner: CS/GTM
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

### Runbook 9: `nrr` breach

- Trigger threshold: <100%=red, 100-115%=yellow, >115%=green
- Incident owner: Finance
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

### Runbook 10: `sales_cycle_days` breach

- Trigger threshold: >90=red, 60-90=yellow, <60=green
- Incident owner: GTM lead
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

### Runbook 11: `proposal_acceptance_rate` breach

- Trigger threshold: <20%=red, 20-35%=yellow, >35%=green
- Incident owner: Founder/GTM
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

### Runbook 12: `pilot_scope_change_rate` breach

- Trigger threshold: >30%=red, 15-30%=yellow, <15%=green
- Incident owner: Solutions lead
- Immediate actions (0-24h):
  - validate metric integrity
  - identify stage/segment concentration
  - assign corrective owner
- Follow-up actions (24-72h):
  - run targeted intervention
  - measure short-term impact
  - update decision log
- Escalation condition:
  - two consecutive red periods
- Escalation audience:
  - founder + GTM + solutions

---

## Completion criteria

KPI operating system v1 is complete when all core KPIs have active dashboards, owners, thresholds, and runbooks in weekly operation.
