# World-Class Release-Critical Ownership Map

This document starts implementation of the "Assign owners for every release-critical workflow" checklist item in the World-Class Quality Program.

## Ownership map

| Workflow | Primary owner | Backup owner | Trigger | Evidence output |
| --- | --- | --- | --- | --- |
| CI quality gate health | QA Platform Lead | Dev Experience Lead | Every PR + mainline commit | Gate status summary |
| Security baseline and vuln checks | Security Champion | QA Platform Lead | Daily + release candidate | Security scan bundle |
| Release readiness board | Release Manager | Product Engineering Lead | At release candidate cut | Readiness board snapshot |
| Changelog + narrative quality | Product Engineering Lead | Release Manager | Pre-tag | Changelog and release narrative |
| Evidence pack generation | QA Platform Lead | Release Manager | Pre-tag | Evidence pack artifact |
| Rollback/runbook verification | SRE/Operations Owner | Release Manager | Pre-tag and post-release window | Runbook verification log |

## Escalation policy

- Any red gate on a release candidate is escalated immediately in the release channel.
- If primary owner is unavailable for more than 4 business hours during release impact, backup owner assumes authority.
- Tagging is blocked until all workflows have either a green status or an explicit, documented exception approved by two owners.

## RACI shorthand

- **R** (Responsible): primary owner in table.
- **A** (Accountable): Release Manager for final ship/no-ship decision.
- **C** (Consulted): Product Engineering Lead and Security Champion.
- **I** (Informed): broader maintainer group.

## Next iteration

- Replace role-based owner labels with named maintainers.
- Link each workflow to an executable CI job and runbook path.
- Publish a monthly "ownership drift" check in trust review.
