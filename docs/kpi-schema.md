# Top-tier KPI schema (v1)

This page defines the weekly KPI contract for CTO/dashboard reporting and links to the machine-readable schema.

## Contract artifacts

- JSON schema: [`docs/kpi-schema.v1.json`](kpi-schema.v1.json)
- First seed baseline instance: [`docs/kpi-baseline-week-2026-04-17.md`](kpi-baseline-week-2026-04-17.md)

## KPI keys (required)

1. `first_time_success_onboarding_rate`
2. `median_release_decision_time`
3. `failed_release_gate_frequency`
4. `rollback_rate`
5. `mean_time_to_triage_first_failure`
6. `docs_to_adoption_conversion`

## Metric object contract

Each KPI key MUST use this shape:

- `value` (number/string/null)
- `unit` (string)
- `sample_size` (integer/null)
- `quality` (`seed` | `provisional` | `stable`)
- `source` (string)

## Program-level required fields

- `schema_version` (currently `1.0.0`)
- `week_ending` (ISO date)
- `program_status` (`green`/`amber`/`red`)
- `kpis` (object with all 6 required keys)

## Versioning and change rules

- **PATCH:** wording-only clarifications, no field-level behavior changes.
- **MINOR:** additive optional fields.
- **MAJOR:** required-field or semantic changes.

Compatibility expectation: downstream consumers should be able to parse all `1.x` payloads without breaking if they ignore unknown optional fields.

## Minimum weekly validation workflow

```bash
python scripts/check_repo_layout.py
python -m pytest -q tests/test_phase1_hardening.py
```

## Ownership

- KPI schema DRI: Platform engineering
- KPI interpretation DRI: Product + DX
- Weekly approval cadence: Friday closeout
