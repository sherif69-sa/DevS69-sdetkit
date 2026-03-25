# CLI

DevS69 SDETKit is organized around four umbrella kits. Use these first.

## Primary product surface (umbrella kits)

1. **Release Confidence Kit**: `sdetkit release ...`
2. **Test Intelligence Kit**: `sdetkit intelligence ...`
3. **Integration Assurance Kit**: `sdetkit integration ...`
4. **Failure Forensics Kit**: `sdetkit forensics ...`
5. **Kit discovery**: `sdetkit kits list` and `sdetkit kits describe <kit>`

### First-run hero commands

- `sdetkit kits list`
- `sdetkit release gate fast`
- `sdetkit release gate release`
- `sdetkit intelligence flake classify --history examples/kits/intelligence/flake-history.json`
- `sdetkit integration check --profile examples/kits/integration/profile.json`
- `sdetkit integration topology-check --profile examples/kits/integration/heterogeneous-topology.json`
- `sdetkit forensics compare --from examples/kits/forensics/run-a.json --to examples/kits/forensics/run-b.json`

## Compatibility and supporting surfaces

Legacy direct commands remain fully supported for backward compatibility:

- `gate`, `doctor`, `security`, `repo`, `evidence`, `report`, `policy`

Supporting utilities remain available, but are no longer the primary discovery surface:

- `kv`, `apiget`, `cassette-get`, `patch`, `maintenance`, `ops`, `notify`, `agent`

Playbook and transition-era lanes are preserved but intentionally secondary:

- `sdetkit playbooks`
- legacy compatibility lanes and archived transition commands
- canonical rename map: [public-surface-rename-map](public-surface-rename-map.md)

## Contract expectations

Public kit commands are contract-oriented:

- Machine-readable JSON with `schema_version`
- Deterministic ordering and reproducible artifacts
- Stable exit code lanes (`0` success, `1` policy/contract failure, `2` invalid input/usage)

## References

- [Command taxonomy](command-taxonomy.md)
- [Command surface](command-surface.md)
- [Umbrella architecture](architecture/umbrella-kits.md)
- [Release kit](kits/release-confidence.md)
- [Intelligence kit](kits/test-intelligence.md)
- [Integration kit](kits/integration-assurance.md)
- [Forensics kit](kits/failure-forensics.md)

## reliability-evidence-pack

--day15-summary
--day16-summary
--day17-summary
--min-reliability-score
--write-defaults
--execute
--evidence-dir
--timeout-sec
--emit-pack-dir

## objection-handling

--docs-page
--min-faq-score
--execute
--evidence-dir
--timeout-sec
--emit-pack-dir
