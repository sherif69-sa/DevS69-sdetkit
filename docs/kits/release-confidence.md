# Release Confidence Kit

## Purpose
Provide deterministic release gating, diagnostics, and evidence outputs for release owners.

## Inputs
Repository source tree, policy/config files, and optional CI metadata.

## Outputs
Gate/doctor/security/evidence JSON/SARIF/manifests from existing stable commands.

## CI role
Primary merge and release confidence decision lane.

## Hero commands
```bash
sdetkit release gate fast
sdetkit release gate release
sdetkit release doctor
sdetkit release evidence --help
```
