# Failure Forensics Kit

## Purpose
Provide deterministic run comparison and minimal repro bundle packaging.

## Inputs
Two run JSON files (`report` schema) and optional extra evidence files.

## Outputs/artifacts
- `sdetkit.forensics.compare.v1`
- `sdetkit.forensics.bundle.v1`

## CI role
Summarize regressions/resolutions and preserve reproducible failure bundles.

## Example commands
```bash
sdetkit forensics compare --from examples/kits/forensics/run-a.json --to examples/kits/forensics/run-b.json
sdetkit forensics bundle --run examples/kits/forensics/run-b.json --output build/repro.zip
```
