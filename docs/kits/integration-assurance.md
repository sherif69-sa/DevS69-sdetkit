# Integration Assurance Kit

## Purpose
Provide offline-first confidence that runtime dependencies are actually ready.

## Inputs
- Readiness profile JSON (`required_env`, `required_files`, `services`)
- Topology profile JSON (`topology.application_services`, `topology.data_services`, `topology.mocked_platforms`)
- Cassette JSON for replay contract validation

## Outputs / artifacts
- `sdetkit.integration.profile-check.v1`
- `sdetkit.integration.matrix.v1`
- `sdetkit.integration.topology-check.v1`
- `sdetkit.integration.cassette-validate.v1`

## Exit-code contract
- `0`: all checks passed / compatible
- `1`: readiness or cassette contract failure
- `2`: invalid profile/cassette input

## CI role
Fail fast before expensive integration runs, validate heterogeneous enterprise topologies, and verify replay cassettes are valid and deterministic.

## Example
```bash
sdetkit integration topology-check --profile examples/kits/integration/heterogeneous-topology.json
sdetkit integration cassette-validate --cassette .sdetkit/cassettes/sample.json
```
