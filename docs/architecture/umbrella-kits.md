# Umbrella architecture: SDETKit kits

SDETKit now exposes four explicit kits under one umbrella CLI:

- **Release Confidence Kit** (`sdetkit release ...`): gate, doctor, security, evidence, repo readiness.
- **Test Intelligence Kit** (`sdetkit intelligence ...`): flake classification, deterministic env capture, impact summaries, mutation governance checks.
- **Integration Assurance Kit** (`sdetkit integration ...`): profile-driven environment checks and compatibility summaries.
- **Failure Forensics Kit** (`sdetkit forensics ...`): run-to-run compare and deterministic repro bundle generation.

## Product boundaries

- **Stable/Core**: release, intelligence, integration, and existing direct commands (`gate`, `doctor`, `repo`, `security`, `evidence`).
- **Experimental**: forensics bundle/compare lane is real and deterministic, but staged for expansion.
- **Backward compatibility**: existing stable commands remain first-class; kit commands are additive grouping aliases.

## Deterministic artifact contracts

Every new kit command emits machine-readable JSON with `schema_version` and deterministic ordering.
