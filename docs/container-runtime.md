# Container runtime contract (adoption-focused)

SDETKit now includes an adopter-oriented runtime container definition: `Dockerfile.runtime`.

This is distinct from the repository's maintainer/test container workflow and is intended for external teams that want a predictable CLI runtime surface.

## Build runtime image

```bash
docker build -f Dockerfile.runtime -t sdetkit-runtime .
```

## Verify runtime contract (machine-readable)

```bash
docker run --rm -v "$PWD":/workspace -w /workspace sdetkit-runtime contract runtime --format json
```

Expected high-value fields in output:
- `runtime_contract_version`
- `tool` (`name`, `version`)
- `canonical_first_path`
- `stable_machine_outputs.review_operator_json.contract_version`

## Run stable operator integration surface

```bash
docker run --rm -v "$PWD":/workspace -w /workspace sdetkit-runtime review . --no-workspace --format operator-json
```

Use this command in CI/jobs when you want a long-lived operator-facing JSON parsing surface.

## Local (non-container) equivalent

```bash
python -m sdetkit contract runtime --format json
python -m sdetkit review . --no-workspace --format operator-json
```
