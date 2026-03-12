# Doctor

`doctor` is a deterministic readiness verifier for release confidence.

## Commands

- `sdetkit doctor --all --format json`
- `sdetkit doctor --dev --ci --deps --clean-tree --repo --format md`
- `sdetkit doctor --only pyproject --format json`

## Contract

- JSON output includes `schema_version: sdetkit.doctor.v2`.
- Stable check IDs and deterministic JSON ordering.
- Explicit failure classification in JSON error payloads (for example: `plan_id_mismatch`).
- Exit codes:
  - `0`: all selected checks passed
  - `2`: one or more selected checks failed, or contract mismatch in apply-plan flow

## Real-world depth

`doctor` checks production-relevant failure modes:

- toolchain availability and virtualenv posture
- dependency graph consistency
- repo cleanliness + release metadata
- CI + governance file integrity
- stdlib-shadowing and non-ASCII hygiene

Each failing check includes actionable remediation (`fix`) and supporting evidence.

## Determinism

- Baseline snapshots are emitted with stable key ordering.
- Check collections are explicitly ordered.
- Snapshot diff output is normalized for reproducible CI gating.
