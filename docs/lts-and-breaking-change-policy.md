# Long-Term Support (LTS) & Breaking-Change Policy (P2.3)

Status: Active policy (v1)
Effective date: 2026-04-16

## Objective

Provide clear support windows and deprecation/breaking-change governance so enterprise adopters can plan upgrades with predictable risk.

## Support lifecycle

### Release channels

- **Current:** latest minor release line.
- **LTS:** designated stable line for enterprise teams requiring slower upgrade cadence.
- **Legacy:** out-of-support lines retained only for historical reference.

### Support windows

- Current line: support until next 2 minor releases are published.
- LTS line: support for 12 months from LTS designation date.
- Legacy line: no active fixes; security exceptions only at maintainer discretion.

## Breaking-change governance

### What counts as breaking

- Removal/rename of public commands in stable contract tiers.
- Schema-incompatible changes to published machine-readable artifacts.
- Behavior changes that invalidate documented canonical flows.

### Required process

1. Publish deprecation notice with migration path.
2. Announce timeline in release notes and support docs.
3. Keep compatibility shim for minimum deprecation window.
4. Validate migration via contract checks before removal.

### Minimum deprecation windows

- Tier-A stable command surfaces: **2 minor releases**.
- Tier-B supported surfaces: **1 minor release**.
- Tier-C experimental surfaces: best effort with explicit warning.

## Release communication checklist (support-window aware)

Before every minor release:

- [ ] State current + LTS + legacy support lines explicitly.
- [ ] List deprecations introduced and effective removal versions.
- [ ] Link migration guides for each impacted command/contract.
- [ ] Confirm whether any breaking changes are planned for next release.
- [ ] Publish owner contact path for upgrade support.

For breaking releases (if any):

- [ ] Publish "impact summary" table (what changed, who is affected, migration effort).
- [ ] Provide rollback strategy and compatibility fallback window.
- [ ] Run and publish contract regression checks.

## Exception policy

- Emergency security break/fix exceptions can override timelines with documented rationale.
- Every exception must include:
  - approver
  - impacted versions
  - expiry date
  - remediation/migration plan

## Machine-readable policy contract

See `docs/contracts/support-lifecycle-policy.v1.json`.

## Acceptance criteria (P2.3)

- [x] LTS/support-window policy documented.
- [x] Breaking/deprecation governance documented.
- [x] Release communication checklist documented.
- [x] Machine-readable support policy contract published.
