# Adaptive Ops Summary

Generated at: 2026-04-16T17:30:54.481386+00:00

## Scenario coverage
- Total scenarios: **1895**
- Meets target: **True**

## Postcheck status
- OK: **True**
- Required failures: **0**
- Warnings: **1**

## Doctor snapshot
- Doctor OK: **True**
- Doctor score: **100**
- Failed checks: **3**

## First-run triage hints
- Hint count: **3**

- doctor: Ensure pyproject.toml is valid and includes project metadata required by doctor.
- doctor: Create/activate .venv and install project deps before running gates.
- doctor: Install required dev tools (ruff/mypy/pytest) via bootstrap/install lanes.
