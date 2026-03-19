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

## Choose your SDET lane fast

- **Release confidence**: use when you need go/no-go readiness, repo health signals, and approval evidence.
- **Test intelligence**: use when you need smarter triage for flakes, failure clustering, impact analysis, or reproducible env capture.
- **Integration assurance**: use when you need stronger service-profile checks, environment readiness validation, and topology-aware contracts.
- **Failure forensics**: use when you need run-to-run diffs, repro bundles, and escalation-ready evidence packs.

For a fuller capability map, run:

```bash
python -m sdetkit kits list
python -m sdetkit kits describe release
python -m sdetkit kits describe intelligence
python -m sdetkit kits describe integration
python -m sdetkit kits describe forensics
python -m sdetkit intelligence upgrade-audit --format json --top 5
```

## Hero commands

```bash
python -m sdetkit kits list
python -m sdetkit release gate release
python -m sdetkit intelligence failure-fingerprint --failures examples/kits/intelligence/failures.json
python -m sdetkit integration check --profile examples/kits/integration/profile.json
python -m sdetkit integration topology-check --profile examples/kits/integration/heterogeneous-topology.json
# validates service owners, dependency edges, mocked platform coverage, deployments, telemetry, and data resilience
bash premium-gate.sh --mode full
# premium gate now emits .sdetkit/out/integration-topology.json as a first-class operational artifact
python -m sdetkit forensics compare --from examples/kits/forensics/run-a.json --to examples/kits/forensics/run-b.json --fail-on error
python -m sdetkit forensics bundle --run examples/kits/forensics/run-b.json --output build/repro.zip
python -m sdetkit continuous-upgrade-cycle9-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle10-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle11-closeout --format json --strict
```

## Upgrade planning (first step)

Run a dependency-manifest audit against PyPI to identify candidate upgrades, detect cross-file version drift, and prioritize the highest-signal upgrade gaps. The audit now surfaces the repo baseline version, estimated version-gap size (major/minor/patch), release recency, an ordered risk score, recommended maintenance lanes, manifest actions, suggested target versions, and floor-and-lock baseline detection for repos that intentionally mix flexible ranges with tested pins. You can invoke it from either the standalone script or the primary Intelligence kit surface, and you can fail CI at a chosen signal threshold:

```bash
make upgrade-audit
python -m sdetkit intelligence upgrade-audit --format json --top 5
python -m sdetkit intelligence upgrade-audit --format md --offline
python scripts/upgrade_audit.py --format json > build/upgrade-audit.json
python scripts/upgrade_audit.py --fail-on high
python scripts/upgrade_audit.py --cache-ttl-hours 6 --max-workers 12
python scripts/upgrade_audit.py --offline --format md
python scripts/upgrade_audit.py --signal high --policy blocked --top 5
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
