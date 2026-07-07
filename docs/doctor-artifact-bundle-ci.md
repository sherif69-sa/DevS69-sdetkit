# Doctor artifact bundle CI guide

This guide describes the current review-first Doctor artifact bundle path for CI and local operators.

## Goal

The artifact directory should collect the files an operator needs to inspect repository health without granting automation authority. The bundle is evidence for review, not permission to patch, merge, dismiss security findings, or claim semantic equivalence.

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

## Expected files

The base bundle writes:

- `build/sdetkit/doctor-report.json`
- `build/sdetkit/doctor-report.md`
- `build/sdetkit/doctor-report-manifest.json`

When a FailureVector bundle is supplied, the bundle also writes:

- `build/sdetkit/failure-vector.json`

## Review-first boundary

The Doctor report and artifact bundle must keep these authority fields false:

- `automation_allowed`
- `patch_application_allowed`
- `security_dismissal_allowed`
- `merge_authorized`
- `semantic_equivalence_claim`

A reviewer may use the bundle to decide the next action, but the bundle itself does not authorize a change.

## CI upload pattern

A CI workflow can upload `build/sdetkit` as an artifact after the Doctor command runs. The manifest should be treated as the index file for the bundle because it records output paths and SHA-256 digests.
