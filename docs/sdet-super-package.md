# SDET Super Package

This package defines three distinct SDET kits that can be rolled out independently and combined for enterprise-grade release confidence.

## Kit 1: Reliability Gate Kit

Owns deterministic release confidence outcomes for every change.

Core lanes:

- `python -m sdetkit gate fast`
- `python -m sdetkit gate release`
- `python -m sdetkit security enforce --json --out build/security-enforce.json`

## Kit 2: Integration Contract Kit

Owns API and service contract integrity with replay-first validation.

Core lanes:

- `python -m sdetkit apiget --help`
- `python -m pytest -q tests/test_apiget_request_builder.py tests/test_cassette.py`
- `python -m pytest -q tests/test_apiclient_async_pagination.py`

## Kit 3: Performance + Chaos Kit

Owns resilience, recovery, and budget enforcement under stress.

Core lanes:

- `python -m sdetkit doctor --format json`
- `python -m pytest -q tests/test_control_plane_ops.py tests/test_reliability_evidence_pack.py`
- `python -m pytest -q tests/test_doctor_diagnostics.py`

## Platform components

- Unified evidence directory for all kit outputs.
- Deterministic CI workflow templates with artifact upload.
- Mandatory strict mode checks for release branches.

## Rollout order

1. Land Reliability Gate Kit as baseline gate.
2. Add Integration Contract Kit to reduce external-service regressions.
3. Add Performance + Chaos Kit before high-scale or enterprise rollout.
