# CLI reference

This page is the **current CLI reference for command discovery** and mirrors the front-door product story: release confidence first, expansion second.

**Primary outcome:** know if a change is ready to ship.

**Canonical first path:** `python -m sdetkit gate fast` → `python -m sdetkit gate release` → `python -m sdetkit doctor`.

It intentionally prioritizes:

1. the canonical public/stable first-time path,
2. stability-aware expansion into advanced surfaces,
3. clear demotion of transition-era or legacy-oriented material.

## Canonical first-time path (public / stable)

Use this exact sequence first:

1. `python -m sdetkit gate fast`
2. `python -m sdetkit gate release`
3. `python -m sdetkit doctor`

This is the primary product path for first-time adoption and release-confidence proof. If a new visitor remembers only one thing, it should be this exact path.

## Stability-aware command discovery

After the canonical path is working, expand deliberately:

### Advanced but supported

- Umbrella kits: `sdetkit kits list`, `sdetkit kits describe <kit>`
- Release Confidence Kit: `sdetkit release ...`
- Test Intelligence Kit: `sdetkit intelligence ...`
- Integration Assurance Kit: `sdetkit integration ...`
- Failure Forensics Kit: `sdetkit forensics ...`

### Public/stable compatibility aliases (secondary for discovery)

These remain fully supported for existing automation and muscle memory:

- `gate`, `doctor`, `security`, `repo`, `evidence`, `report`, `policy`

### Supporting utilities (secondary)

Available utility lanes include:

- `kv`, `apiget`, `cassette-get`, `patch`, `maintenance`, `ops`, `notify`, `agent`

## Transition-era and legacy-oriented material

Transition-era and archived lanes remain available for compatibility, but they are **not** first-time entrypoints and should not dominate discovery:

- `sdetkit playbooks`
- archived transition commands and legacy compatibility lanes
- canonical rename map: [public-surface-rename-map](public-surface-rename-map.md)
- historical material: [archive index](archive/index.md)

## Legacy migration hints (runtime behavior)

When a legacy compatibility command is invoked, the CLI can emit a migration hint to stderr with a preferred next surface and a canonical-path reminder.

Controls:

- **Default behavior:** hints are enabled.
- **Environment toggle:** set `SDETKIT_LEGACY_HINTS=0` (also `false|no|off`) to disable.
- **Per-invocation override:** pass `--no-legacy-hint` for one command run.

Examples:

```bash
# one command only (preferred in CI scripts when needed)
python -m sdetkit --no-legacy-hint phase1-hardening

# shell/session level behavior
SDETKIT_LEGACY_HINTS=0 python -m sdetkit phase1-hardening
```

For migration planning and lane mapping, see [Legacy command migration map](legacy-command-migration-map.md).

You can also query migration guidance directly:

```bash
python -m sdetkit legacy migrate-hint phase1-hardening
python -m sdetkit legacy migrate-hint --format json phase1-hardening
python -m sdetkit legacy migrate-hint --all --format json
```

JSON output includes `schema_version`, `mode`, and migration recommendation fields (including `deprecation_horizon`) for automation parsing.

## Contract expectations

Public kit commands are contract-oriented:

- machine-readable JSON with `schema_version`
- deterministic ordering and reproducible artifacts
- stable exit-code lanes (`0` success, `1` policy/contract failure, `2` invalid input/usage)

## Related references

- [Command surface inventory (stability-aware)](command-surface.md)
- [Stability levels](stability-levels.md)
- [Versioning and support posture](versioning-and-support.md)
- [Command taxonomy](command-taxonomy.md)
- [Umbrella architecture](architecture/umbrella-kits.md)
