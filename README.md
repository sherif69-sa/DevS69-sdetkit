# DevS69 SDETKit

DevS69 SDETKit is a unified SDET platform for:

1. **release confidence**
2. **test intelligence**
3. **integration assurance**
4. **failure forensics**

It turns CI and test signals into deterministic contracts, machine-readable artifacts, and clear go/no-go guidance.

## Umbrella kits (primary surface)

- **Release Confidence Kit** — `sdetkit release ...`
- **Test Intelligence Kit** — `sdetkit intelligence ...`
- **Integration Assurance Kit** — `sdetkit integration ...`
- **Failure Forensics Kit** — `sdetkit forensics ...`
- **Catalog** — `sdetkit kits list` / `sdetkit kits describe <kit>`

## Hero commands

```bash
python -m sdetkit kits list
python -m sdetkit release gate release
python -m sdetkit intelligence failure-fingerprint --failures examples/kits/intelligence/failures.json
python -m sdetkit integration check --profile examples/kits/integration/profile.json
python -m sdetkit forensics compare --from examples/kits/forensics/run-a.json --to examples/kits/forensics/run-b.json --fail-on error
python -m sdetkit forensics bundle --run examples/kits/forensics/run-b.json --output build/repro.zip
python -m sdetkit continuous-upgrade-cycle9-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle10-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle11-closeout --format json --strict
```

## Upgrade planning (first step)

Run a direct dependency audit against PyPI to identify candidate upgrades:

```bash
make upgrade-audit
```

## Sample artifacts

- `examples/kits/intelligence/*`
- `examples/kits/integration/profile.json`
- `examples/kits/forensics/run-a.json`
- `examples/kits/forensics/run-b.json`

## Backward compatibility

Existing direct commands remain supported (`gate`, `doctor`, `security`, `repo`, `evidence`, `report`, `policy`, etc.).
They are preserved compatibility lanes; umbrella kits are the primary discovery and product entrypoint.

See `docs/migration-compatibility-note.md` for migration and experimental-status notes.

## Quality transformation

For the execution blueprint to reach a world-class quality bar across all bundled offerings, see `docs/world-class-quality-program.md`.
