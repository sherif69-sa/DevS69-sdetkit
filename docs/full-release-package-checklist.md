# Full release package checklist

Use this checklist before approving an organization-level rollout or major release train.

## 1) Product readiness

- [ ] Canonical path artifacts attached (`gate-fast.json`, `release-preflight.json`, `doctor.json`).
- [ ] Release confidence decision recorded (`ship` / `no-ship`) with owner sign-off.
- [ ] KPI snapshot attached for the release window (`docs/kpi-weekly-<date>.json`).

## 2) Documentation readiness

- [ ] Release notes drafted and reviewed.
- [ ] Migration/compatibility notes updated.
- [ ] Operator runbook links verified (`operations-handbook.md`, escalation model, policy matrix).

## 3) Security and compliance readiness

- [ ] Security scan outputs attached (or exception record approved).
- [ ] Dependency/update exceptions documented.
- [ ] Compliance controls impacted by release are reviewed and signed.

## 4) Support readiness

- [ ] Severity owner and incident commander on-call for release window.
- [ ] Escalation communication template pre-filled.
- [ ] Rollback owner and rollback window documented.

## 5) Communications readiness

- [ ] Internal stakeholder announcement drafted.
- [ ] External/customer comms plan prepared if user-visible impact exists.
- [ ] Leadership summary entry prepared for weekly/monthly reporting.

## 6) Final go/no-go gate

- [ ] All critical checklist items are complete or have approved exception links.
- [ ] Release owner + platform owner + QA governance signoff captured.
- [ ] Evidence bundle archived in release artifacts.

## Evidence bundle index (minimum)

- `build/gate-fast.json`
- `build/release-preflight.json`
- `build/doctor.json`
- `docs/kpi-weekly-<date>.json`
- `docs/executive-weekly-<date>.md`
- portfolio scorecard for the same window
