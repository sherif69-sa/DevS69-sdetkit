# Command surface inventory (stability-aware)

SDETKit's public surface is unified around the canonical public/stable first-time path, with advanced and compatibility lanes secondary.

## Command-family contract snapshot

This table is sourced from `src/sdetkit/public_surface_contract.py`.

<!-- BEGIN:PUBLIC_SURFACE_CONTRACT_TABLE -->

| Command family | Purpose | Stability tier | First-time adopter default? | Transition-era / legacy-oriented? |
|---|---|---|---|---|
| `release-confidence-canonical-path` | Primary first-time product surface for deterministic shipping readiness and release confidence. | Public / stable | Yes | No |
| `umbrella-kits` | Umbrella kits remain fully supported for expanded release, intelligence, integration, and forensics workflows. | Advanced but supported | No | No |
| `compatibility-aliases` | Backward-compatible direct lanes preserved for existing automation and muscle memory. | Public / stable | No | No |
| `supporting-utilities-and-automation` | Supporting utilities and automation lanes; useful but intentionally secondary to the canonical public/stable first-time path. | Advanced but supported | No | No |
| `playbooks` | Guided adoption and rollout lanes for operational outcomes. | Advanced but supported | No | No |
| `experimental-transition-lanes` | Transition-era and legacy-oriented lanes retained for compatibility. | Experimental / incubator | No | Yes |

<!-- END:PUBLIC_SURFACE_CONTRACT_TABLE -->

## First-time path (public / stable)

1. `python -m sdetkit gate fast`
2. `python -m sdetkit gate release`
3. `python -m sdetkit doctor`

## Compatibility path

Direct commands stay stable and supported:

- `gate`, `doctor`, `security`, `repo`, `evidence`, `report`, `policy`

Use these for existing scripts while keeping first-time discovery/docs on the canonical path.

## Supporting and experimental

- Supporting utilities: `kv`, `apiget`, `cassette-get`, `patch`, `maintenance`, `dev`, `ci`, `ops`, `notify`, `agent`
- Playbooks catalog: `sdetkit playbooks`
- Transition-era lanes: legacy compatibility lanes and archived transition commands
- Canonical rename map: [public-surface-rename-map](public-surface-rename-map.md)

Maintainer sync:

- Regenerate/check the table with `python tools/render_public_surface_contract_table.py --check`.
