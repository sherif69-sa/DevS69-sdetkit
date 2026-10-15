# SDETKit capability map and command taxonomy

## Product thesis

SDETKit's primary product promise is deterministic release confidence from one canonical first path:

1. `sdetkit gate fast`
2. `sdetkit gate release`
3. `sdetkit doctor`

After this path is trusted in your repo, expand into umbrella kit workflows for deeper operational outcomes:

- **Release confidence** (`sdetkit release ...`)
- **Test intelligence** (`sdetkit intelligence ...`)
- **Integration assurance** (`sdetkit integration ...`)
- **Failure forensics** (`sdetkit forensics ...`)

Use `sdetkit kits list` to discover these expansion surfaces.

## Command discovery order (recommended)

Use this order to reduce decision fatigue during adoption:

1. **First run (always):** `sdetkit gate fast` -> `sdetkit gate release` -> `sdetkit doctor`
2. **Capability expansion:** `sdetkit kits list` then choose `release|intelligence|integration|forensics`
3. **Operational depth:** move into stable supporting lanes (`security`, `repo`, `evidence`, `report`, `policy`)
4. **Remediation:** `sdetkit diagnose run --log <ci-log> --prove`, then `sdetkit diagnose decide`

## Layer 1: Canonical release-confidence path (public/stable first-run)

- `sdetkit gate fast`
- `sdetkit gate release`
- `sdetkit doctor`

These commands are the default onboarding and adoption lane.

## Layer 2: Umbrella kits (advanced but supported expansion)

- `sdetkit kits list`
- `sdetkit kits discover --goal "<goal>" --query "<query>"`
- `sdetkit kits describe <kit>`
- `sdetkit release ...`
- `sdetkit intelligence ...`
- `sdetkit integration ...`
- `sdetkit forensics ...`

## Layer 3: Stable supporting lanes (post-first-run)

These remain fully supported for daily operations and automation after the canonical first run:

- `sdetkit security ...`
- `sdetkit repo ...`
- `sdetkit evidence ...`
- `sdetkit report ...`
- `sdetkit policy ...`

## Layer 4: Supporting utilities and integrations

- Utilities: `kv`, `apiget`, `cassette-get`, `patch`
- Operations: `maintenance`, `ops`, `notify`, `ci`, `dev`

## Legacy and transition-lane boundary

- Prefer stable lanes when an equivalent command exists.
- Treat transition-era lanes as compatibility workflows for existing automation and historical continuity.

For the full command inventory, run `sdetkit --help`; [CLI reference](cli.md) lists the commands removed in the CLI cleanup.
