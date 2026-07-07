# Doctor artifact bundle CI guide

This guide describes the current Doctor artifact bundle path for CI and local operators.

## Goal

The artifact directory should collect the files an operator needs to inspect repository health. The bundle supports review and local decision-making; it does not replace maintainer judgment.

The CI guide closes the operating gap between the Doctor report contract, FailureVector input, and the self-contained `build/sdetkit` directory introduced by the Doctor artifact bundle work.

## Recommended command

```bash
python -m sdetkit doctor --report-contract --report-artifact-dir build/sdetkit
```

When a prebuilt FailureVector bundle exists, pass it explicitly:

```bash
python -m sdetkit doctor --report-contract \
  --failure-vector-bundle build/sdetkit/failure-vector.json \
  --report-artifact-dir build/sdetkit
```

The Doctor command should run after the job has produced any FailureVector bundle it wants Doctor to summarize. Doctor does not parse logs directly in this path; it consumes the prebuilt bundle as input.

## Expected files

The base bundle writes:

- `build/sdetkit/doctor-report.json`
- `build/sdetkit/doctor-report.md`
- `build/sdetkit/doctor-report-manifest.json`

When a FailureVector bundle is supplied, the bundle also writes:

- `build/sdetkit/failure-vector.json`

The manifest is the stable index for the directory. CI consumers should read the manifest before reading individual files so the output set can grow without breaking the directory layout.

## Minimum CI assertions

A workflow can make these lightweight assertions before uploading the directory:

```bash
test -f build/sdetkit/doctor-report.json
test -f build/sdetkit/doctor-report.md
test -f build/sdetkit/doctor-report-manifest.json
python -m json.tool build/sdetkit/doctor-report.json >/dev/null
python -m json.tool build/sdetkit/doctor-report-manifest.json >/dev/null
```

When the optional FailureVector file is expected, also assert:

```bash
test -f build/sdetkit/failure-vector.json
python -m json.tool build/sdetkit/failure-vector.json >/dev/null
```

## CI upload pattern

A CI workflow can upload `build/sdetkit` as an artifact after the Doctor command runs. The manifest should be treated as the index file for the bundle because it records output paths and SHA-256 digests.

A practical upload step should name the artifact after the job or Python version, for example `doctor-artifacts-py3.12`, so parallel lanes remain easy to inspect.

## Completion signal

A Doctor artifact bundle PR is complete when:

- the focused Doctor report tests pass,
- the generated directory shape is documented,
- the manifest records every generated output,
- optional FailureVector input remains explicit,
- and no default Doctor command behavior changes unexpectedly.
