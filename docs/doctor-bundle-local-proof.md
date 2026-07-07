# Doctor bundle local proof guide

This guide gives maintainers a local proof path for Doctor report bundle changes.

## Focus

Use this guide when a PR changes the Doctor report bundle, its generated files, or documentation around bundle usage.

A good local proof should answer these questions:

- Does the focused test suite pass?
- Does the repository formatter/linter accept the change?
- Can the bundle be generated locally?
- Can the generated JSON files be parsed?
- Does the manifest describe the files in the directory?

## Baseline proof

Run focused tests first:

```bash
python -m pytest -q tests/test_doctor_report_cli_contract.py -o addopts=
```

When the bundle output helper changes, also run:

```bash
python -m pytest -q tests/test_doctor_bundle_outputs.py -o addopts=
```

Then run formatting and linting through the repository guardrail:

```bash
python -m pre_commit run -a
```

## Bundle generation proof

Generate the base bundle locally:

```bash
python -m sdetkit doctor --report-contract --report-artifact-dir build/sdetkit
```

Confirm the directory contains:

- `doctor-report.json`
- `doctor-report.md`
- `doctor-report-manifest.json`

The report JSON and manifest should both parse as JSON:

```bash
python -m json.tool build/sdetkit/doctor-report.json >/dev/null
python -m json.tool build/sdetkit/doctor-report-manifest.json >/dev/null
```

## Manifest check

Read the manifest first. It should describe every generated output file and include SHA-256 digests so the directory can be checked file by file.

## Review rule

The bundle is a review aid. It should help a maintainer inspect the current state and decide the next safe action.
