# Test Intelligence Kit

## Purpose
Provide deterministic test-quality intelligence beyond simple lint/test wrappers.

## Inputs
- flake history JSON (`tests[].id`, `tests[].outcomes`)
- changed file list + test map JSON
- mutation governance policy JSON

## Outputs/artifacts
- `sdetkit.intelligence.flake.v1`
- `sdetkit.intelligence.impact.v1`
- `sdetkit.intelligence.env-capture.v1`
- `sdetkit.intelligence.mutation-policy.v1`

## CI role
Flag flaky tests, scope impact-driven runs, and enforce mutation governance policy.

## Example commands
```bash
sdetkit intelligence flake classify --history examples/kits/intelligence/flake-history.json
sdetkit intelligence impact summarize --changed examples/kits/intelligence/changed-files.txt --map examples/kits/intelligence/test-map.json
sdetkit intelligence mutation-policy --policy examples/kits/intelligence/mutation-policy.json
```
