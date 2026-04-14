# Support and escalation model

This model defines severity classes, response SLOs, and escalation paths for operating SDETKit as a platform.

## Severity definitions

| Severity | Definition | Example |
|---|---|---|
| Sev-1 Critical | Canonical release path unavailable or unsafe for production decisions | `gate release` unusable across active repos |
| Sev-2 High | Major degradation with workaround but material operational impact | Artifact contract drift breaks reporting |
| Sev-3 Medium | Partial feature issue with bounded impact | Non-critical docs mismatch |
| Sev-4 Low | Cosmetic/documentation/housekeeping issue | Copy or formatting defects |

## Response SLOs

| Severity | Acknowledge | Mitigation plan | Status update cadence |
|---|---|---|---|
| Sev-1 | <= 30 minutes | <= 4 hours | Every 60 minutes |
| Sev-2 | <= 4 hours | <= 1 business day | Every business day |
| Sev-3 | <= 1 business day | <= 5 business days | Twice weekly |
| Sev-4 | <= 3 business days | Next planned cycle | Weekly |

## Escalation chain

1. **Incident commander (Release engineering)** triages and assigns severity.
2. **Owning workstream DRI** leads mitigation.
3. **Platform engineering lead** engages for cross-repo/systemic issues.
4. **Executive sponsor (CTO delegate)** notified for Sev-1 and repeated Sev-2 incidents.

## Incident workflow

1. Open incident record with timestamp, severity, impacted lanes, and rollback risk.
2. Attach evidence artifacts (`gate-fast.json`, `release-preflight.json`, `doctor.json`) where applicable.
3. Publish mitigation plan and next update ETA.
4. Close with root-cause summary and follow-up actions linked to backlog.

## Communication templates

### Initial incident message
- Severity:
- Impacted scope:
- Current mitigation:
- Next update at:

### Resolution message
- Root cause:
- Fix shipped:
- Residual risk:
- Follow-up tasks:

## Ownership and review cadence

| Area | DRI role | Cadence |
|---|---|---|
| Severity policy | Release engineering | Monthly |
| SLO adherence review | Platform engineering | Weekly |
| Executive escalations | CTO delegate + QA governance | Per incident |
