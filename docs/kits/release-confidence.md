# Release Confidence Kit

## Purpose
Provide an opinionated go/no-go decision lane backed by deterministic evidence.

## Inputs
Repository state, policy/config baselines, and CI metadata.

## Outputs / artifacts
Existing core release contracts from `gate`, `doctor`, `security`, and `evidence` including JSON/SARIF/evidence manifests.

## Exit-code contract
- `0`: pass/no blocking release conditions
- `1`: gate/security policy violations where applicable
- `2`: invalid input or execution contract failures

## CI role
Primary release controller for merge and publish decisions.

## Example
```bash
sdetkit release gate release
sdetkit release doctor --format json
sdetkit release evidence pack --output .sdetkit/out/evidence.zip
```
