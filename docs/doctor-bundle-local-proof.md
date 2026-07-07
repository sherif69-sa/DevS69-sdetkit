# Doctor bundle local proof guide

This guide gives maintainers a small local proof path for Doctor report bundle changes.

## Focus

Use this guide when a PR changes the Doctor report bundle, its generated files, or documentation around bundle review.

## Baseline proof

Run focused tests first:

```bash
python -m pytest -q tests/test_doctor_report_cli_contract.py -o addopts=
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

## Review rule

The bundle is a review aid. It should help a maintainer inspect the current state and decide the next safe action.
