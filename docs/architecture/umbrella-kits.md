# Umbrella architecture: SDETKit kits

SDETKit exposes one unified umbrella with four kits:

- **Release Confidence Kit** (`sdetkit release ...`)
- **Test Intelligence Kit** (`sdetkit intelligence ...`)
- **Integration Assurance Kit** (`sdetkit integration ...`)
- **Failure Forensics Kit** (`sdetkit forensics ...`)

## Public-surface policy

- Umbrella kits are the primary discovery and documentation surface.
- Legacy direct commands remain stable compatibility aliases.
- Supporting utilities are intentionally secondary in help/docs.

## Contracts and determinism

Kit commands emit deterministic machine-readable outputs with explicit `schema_version`, stable ordering, and exit code contracts.

## Upgrade blueprint model

`sdetkit kits blueprint --goal "..."` now emits a fuller operating model for umbrella upgrades:

- **architecture layers** — experience surface, AgentOS control plane, and deterministic artifact plane,
- **operating model** — discovery, execution, and review cadences for recurring adoption,
- **upgrade backlog** — prioritized upgrade themes such as umbrella routing, AgentOS promotion, topology assurance, and upgrade-audit integration,
- **metrics** — high-signal operating measures such as routing accuracy, artifact coverage, and AgentOS run success rate.

That turns the umbrella architecture from a static catalog into an execution-ready blueprint for teams that want to scale the repo as a product surface instead of a loose collection of commands.

## Compatibility and migration

Use `docs/migration-compatibility-note.md` for migration guidance and the current experimental summary.
