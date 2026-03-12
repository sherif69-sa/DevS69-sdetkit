# SDETKit capability map and command taxonomy

## Product thesis

SDETKit is a unified SDET platform with four flagship kits:

- **Release confidence** (`sdetkit release ...`)
- **Test intelligence** (`sdetkit intelligence ...`)
- **Integration assurance** (`sdetkit integration ...`)
- **Failure forensics** (`sdetkit forensics ...`)

Start with `sdetkit kits list`.

## Layer 1: Umbrella kits (primary)

- `sdetkit kits list`
- `sdetkit kits describe <kit>`
- `sdetkit release ...`
- `sdetkit intelligence ...`
- `sdetkit integration ...`
- `sdetkit forensics ...`

## Layer 2: Compatibility aliases (stable)

These remain supported for existing automation, but are no longer first-run discovery:

- `sdetkit gate ...`
- `sdetkit doctor ...`
- `sdetkit security ...`
- `sdetkit repo ...`
- `sdetkit evidence ...`
- `sdetkit report ...`
- `sdetkit policy ...`

## Layer 3: Supporting utilities and integrations

- Utilities: `kv`, `apiget`, `cassette-get`, `patch`
- Operations: `maintenance`, `ops`, `notify`, `agent`, `ci`, `dev`

## Layer 4: Playbooks and transition-era lanes

- Guided lanes: `sdetkit playbooks`
- Transition-era compatibility lanes: `dayNN-*`, `*-closeout`, `continuous-upgrade-cycleX-closeout`

Use these intentionally; they are not the flagship product surface.
