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

## Compatibility and migration

Use `docs/migration-compatibility-note.md` for migration guidance and the current experimental summary.
