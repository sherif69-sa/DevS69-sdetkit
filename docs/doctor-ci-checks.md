# Doctor CI checks

This guide lists small checks that can be used around Doctor bundle generation in CI.

## File existence checks

```bash
test -f build/sdetkit/doctor-report.json
test -f build/sdetkit/doctor-report.md
test -f build/sdetkit/doctor-report-manifest.json
```

## JSON checks

```bash
python -m json.tool build/sdetkit/doctor-report.json >/dev/null
python -m json.tool build/sdetkit/doctor-report-manifest.json >/dev/null
```

## Focused tests

```bash
python -m pytest -q tests/test_doctor_report_cli_contract.py -o addopts=
python -m pytest -q tests/test_doctor_bundle_outputs.py -o addopts=
```

## Full repository guardrail

```bash
python -m pre_commit run -a
```

## CI artifact naming

When CI uploads the generated directory, include the job or Python version in the artifact name so parallel runs stay easy to inspect.
