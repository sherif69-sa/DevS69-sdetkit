# Command surface inventory (stability-aware)

SDETKit's public command surface is organized for one coherent product story: release-confidence shipping readiness via one canonical first path.

Primary outcome: know if a change is ready to ship.

1. canonical public/stable first-time path,
2. advanced but supported expansion lanes,
3. compatibility and transition-era lanes kept available but secondary.

## Command-family contract snapshot

This table is sourced from `src/sdetkit/public_surface_contract.py`.

<!-- BEGIN:PUBLIC_SURFACE_CONTRACT_TABLE -->

| Command family | Purpose | Stability tier | First-time adopter default? | Transition-era / legacy-oriented? |
|---|---|---|---|---|
| `release-confidence-canonical-path` | Primary first-time product surface for deterministic shipping readiness; one primary outcome (know if a change is ready to ship) and one canonical command path. | Public / stable | Yes | No |
| `umbrella-kits` | Umbrella kits are fully supported expansion surfaces for release, intelligence, integration, and forensics workflows. | Advanced but supported | No | No |
| `compatibility-aliases` | Backward-compatible direct lanes preserved for existing automation and muscle memory. | Public / stable | No | No |
| `supporting-utilities-and-automation` | Supporting utilities and automation lanes; useful but intentionally secondary to the canonical public/stable first-time path. | Advanced but supported | No | No |
| `playbooks` | Guided adoption and rollout lanes for operational outcomes. | Advanced but supported | No | No |
| `experimental-transition-lanes` | Transition-era and legacy-oriented lanes retained for compatibility and historical continuity. | Experimental / incubator | No | Yes |

<!-- END:PUBLIC_SURFACE_CONTRACT_TABLE -->

## Canonical first-time path (public / stable)

1. `python -m sdetkit gate fast`
2. `python -m sdetkit gate release`
3. `python -m sdetkit doctor`

## Expansion and compatibility (intentionally secondary to first proof)

- Advanced kits and discovery: `sdetkit kits list`, `sdetkit kits describe <kit>`, then `release`, `intelligence`, `integration`, `forensics`
- Compatibility aliases: `gate`, `doctor`, `security`, `repo`, `evidence`, `report`, `policy`
- Supporting utilities and automation: `kv`, `inspect`, `review`, `apiget`, `cassette-get`, `patch`, `maintenance`, `dev`, `ci`, `ops`, `notify`, `agent`, `feature-registry`

## Transition-era and historical lanes

- Playbooks catalog: `sdetkit playbooks`
- Transition-era compatibility lanes and archived commands
- Canonical rename map: [public-surface-rename-map](public-surface-rename-map.md)

Maintainer sync:

- Regenerate/check the table with `python tools/render_public_surface_contract_table.py --check`.
