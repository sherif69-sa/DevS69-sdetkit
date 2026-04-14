# Policy: compatibility and deprecation matrix

This policy defines compatibility guarantees for the SDETKit CLI and core artifact schemas.

## Scope

- CLI canonical path commands
- JSON artifact shape compatibility for release-confidence outputs
- Migration windows for deprecated interfaces

## Compatibility levels

| Level | Meaning | Upgrade expectation |
|---|---|---|
| Stable | No breaking changes without deprecation window | Safe within supported major line |
| Compatible | Behavior may evolve; schema additive changes allowed | Validate in staging before broad rollout |
| Legacy | Supported temporarily for migration only | Move to stable path before sunset date |

## CLI compatibility matrix

| Command / surface | Current level | Policy | Deprecation window |
|---|---|---|---|
| `python -m sdetkit gate fast` | Stable | Output contract remains backward compatible within major version | >= 2 minor releases |
| `python -m sdetkit gate release` | Stable | Exit semantics and core keys (`ok`, `failed_steps`) preserved | >= 2 minor releases |
| `python -m sdetkit doctor` | Stable | Health output remains machine-readable and documented | >= 2 minor releases |
| Legacy command aliases | Legacy | Migration map maintained until sunset | 1 minor release after warning |

## Artifact schema compatibility matrix

| Artifact | Contract level | Required keys | Change policy |
|---|---|---|---|
| `build/gate-fast.json` | Stable | `ok`, `failed_steps`, `profile` | Additive fields allowed; required fields must not be removed in-major |
| `build/release-preflight.json` | Stable | `ok`, `failed_steps`, `profile` | Same as above |
| `build/doctor.json` | Compatible | `ok` | Additional diagnostics may be added without breaking required keys |

## Deprecation process

1. Announce deprecation in docs and release notes with replacement path.
2. Provide automated detection/migration guidance where feasible.
3. Keep deprecated surface active for the published window.
4. Remove only after window closes and migration path has been available.

## Ownership and review cadence

| Policy area | DRI role | Review cadence |
|---|---|---|
| CLI compatibility | Architecture + QA governance | Monthly |
| Artifact schema policy | Platform engineering | Monthly |
| Deprecation announcements | Product + DX | Every release |
