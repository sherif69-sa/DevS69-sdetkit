# Command surface inventory (stability-aware)

SDETKit's public surface is unified around umbrella kits first, compatibility aliases second.

## Command-family contract snapshot

This table is sourced from `src/sdetkit/public_surface_contract.py`.

<!-- BEGIN:PUBLIC_SURFACE_CONTRACT_TABLE -->

| Command family | Purpose | Stability tier | First-time adopter default? | Transition-era / legacy-oriented? |
|---|---|---|---|---|
| `umbrella-kits` | Primary product surface for release confidence, test intelligence, integration assurance, and failure forensics. | Stable/Core | Yes | No |
| `compatibility-aliases` | Backward-compatible direct lanes preserved for existing automation and muscle memory. | Stable/Compatibility | No | No |
| `supporting-utilities-and-automation` | Supporting utilities and automation lanes; useful but intentionally secondary to flagship kits. | Stable/Supporting | No | No |
| `playbooks` | Guided adoption and rollout lanes for operational outcomes. | Playbooks | No | No |
| `experimental-transition-lanes` | Transition-era and legacy-oriented lanes retained for compatibility. | Experimental | No | Yes |

<!-- END:PUBLIC_SURFACE_CONTRACT_TABLE -->

## First-time path

1. `sdetkit kits list`
2. `sdetkit release gate fast`
3. `sdetkit release gate release`
4. `sdetkit intelligence ...`
5. `sdetkit integration ...`
6. `sdetkit forensics ...`

## Compatibility path

Direct commands stay stable and supported:

- `gate`, `doctor`, `security`, `repo`, `evidence`, `report`, `policy`

Use these for existing scripts while migrating discovery/docs to umbrella-kit routes.

## Supporting and experimental

- Supporting utilities: `kv`, `apiget`, `cassette-get`, `patch`, `maintenance`, `dev`, `ci`, `ops`, `notify`, `agent`
- Playbooks catalog: `sdetkit playbooks`
- Transition-era lanes: `dayNN-*`, `*-closeout`, `continuous-upgrade-cycleX-closeout`

Maintainer sync:

- Regenerate/check the table with `python tools/render_public_surface_contract_table.py --check`.
