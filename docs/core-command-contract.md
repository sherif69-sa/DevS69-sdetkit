# Core Command Contract (P0.1)

Status: Active (v1)  
Effective date: 2026-04-16

## Purpose

Define a minimal stable command surface for enterprise rollout so teams can depend on a predictable interface while broader/legacy lanes continue to evolve.

This contract is an implementation artifact for **P0.1** in `docs/enterprise-plan-execution.md`.

## Contract scope

### In scope (stable integration surface)

1. `python -m sdetkit gate fast`
2. `python -m sdetkit gate release`
3. `python -m sdetkit doctor`

These commands are the required front door for pilot and scale adoption.

### Out of scope (for this v1 contract)

- Secondary/advanced workflows (supported but not part of minimal enterprise guarantee).
- Legacy/transition-era commands.
- Internal module implementation details.

## Stability tiers

### Tier A — Core stable contract

- Commands: `gate`, `doctor`
- Compatibility: strongest commitment.
- Change policy: no behavior-breaking changes without deprecation window.

### Tier B — Advanced supported

- Example families: `repo`, `review`, `inspect`, `serve`, `security`, `evidence`.
- Compatibility: supported for production, but may iterate faster than Tier A.
- Change policy: migration guidance required for meaningful UX/contract shifts.

### Tier C — Experimental / legacy

- Transition-era, hidden, and long-tail lanes.
- Compatibility: best effort, opt-in usage only.
- Change policy: may evolve quickly; not suitable for hard enterprise dependencies.

## Deprecation and change-management rules

For Tier A commands:

1. **Announce** deprecation in release notes and docs before behavior removal.
2. **Minimum deprecation window:** 2 minor releases.
3. **Machine-readable warning period:** include deprecation markers in JSON output/help text where applicable.
4. **Migration path required:** provide exact command replacement and example invocation.
5. **Removal gate:** do not remove until docs, CI templates, and quickstarts are updated.

For Tier B commands:

- Minimum deprecation window: 1 minor release.
- Migration note required in changelog/docs.

For Tier C commands:

- Best-effort announcements; removal can be faster but must avoid breaking Tier A onboarding.

## Enforcement artifact

Machine-readable starter manifest:  
`docs/contracts/core-command-contract.v1.json`

This manifest is intended to be consumed by future CI checks to detect unauthorized drift in the enterprise-stable command boundary.

## Acceptance criteria (P0.1)

- [x] Human-readable core command contract published.
- [x] Stability tiers declared.
- [x] Deprecation rules declared.
- [x] Machine-readable manifest published.

## Related docs

- `docs/stability-levels.md`
- `src/sdetkit/public_command_surface.json`
- `docs/enterprise-plan-execution.md`
