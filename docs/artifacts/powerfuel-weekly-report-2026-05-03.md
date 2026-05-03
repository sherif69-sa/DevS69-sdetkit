# Powerfuel Weekly Report (2026-05-03)

Generated at: 2026-05-03T00:00:00Z

## KPI Snapshot
- Workflow count: 53
- Duplicate trigger paths: 111
- First-proof success rate: None
- Time to first proof (median min): None

## Next Retirement Batch (Top 5)
- dependency-audit.yml: score=111 triggers=pull_request,push,schedule,workflow_dispatch
- enforce-branch-protection.yml: score=111 triggers=pull_request,push,schedule,workflow_dispatch
- osv-scanner.yml: score=111 triggers=pull_request,push,schedule,workflow_dispatch
- security-maintenance-bot.yml: score=111 triggers=pull_request,push,schedule,workflow_dispatch
- security.yml: score=111 triggers=pull_request,push,schedule,workflow_dispatch

## Decisions
- Run shadow-mode parity checks on top 5 retirement candidates before workflow removals.
- Keep CI minute/PR KPI null until telemetry source is connected.
