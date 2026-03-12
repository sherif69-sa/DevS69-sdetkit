# Integration Assurance Kit

## Purpose
Validate environment and service readiness contracts with offline-first deterministic checks.

## Inputs
Integration profile JSON (`required_env`, `required_files`, `services`).

## Outputs/artifacts
- `sdetkit.integration.profile-check.v1`
- `sdetkit.integration.matrix.v1`

## CI role
Catch environment drift before integration test execution.

## Example commands
```bash
sdetkit integration check --profile examples/kits/integration/profile.json
sdetkit integration matrix --profile examples/kits/integration/profile.json
```
