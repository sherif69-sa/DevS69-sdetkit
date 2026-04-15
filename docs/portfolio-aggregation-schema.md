# Portfolio aggregation schema versioning convention

This document defines the versioned aggregation contract for portfolio-level readiness reporting across multiple repositories.

## Purpose

- Unblock WS2 portfolio reporting by establishing one schema contract for rollups.
- Ensure weekly executive reporting can evolve without breaking downstream consumers.
- Provide deterministic migration rules for additive and breaking changes.

## Schema identity

- `schema_name`: `sdetkit.portfolio.aggregate`
- `schema_version`: semantic version string (`MAJOR.MINOR.PATCH`)
- Initial version: `1.0.0`

## Version bump policy

| Change type | Example | Required bump | Compatibility expectation |
|---|---|---|---|
| Add optional field | add `risk_tier_breakdown` | MINOR | Backward compatible |
| Clarify constraints only | tighten prose docs | PATCH | Backward compatible |
| Add required field | require `repo_id` | MAJOR | Potentially breaking |
| Rename/remove field | `risk_score` -> `risk_level` | MAJOR | Breaking unless dual-written |

## Required top-level fields

Every portfolio aggregate payload MUST contain:

- `schema_name` (string)
- `schema_version` (string)
- `generated_at` (ISO-8601 UTC timestamp)
- `window` (object with `start_date`, `end_date`)
- `totals` (object)
- `repos` (array)

## `totals` required fields

- `repo_count_total` (integer)
- `repo_count_reporting` (integer)
- `high_risk_repo_count` (integer)
- `medium_risk_repo_count` (integer)
- `low_risk_repo_count` (integer)

## `repos[]` minimum object contract

- `repo_id` (string)
- `risk_tier` (`high` | `medium` | `low`)
- `release_confidence_ok` (boolean)
- `gate_fast_ok` (boolean)
- `gate_release_ok` (boolean)
- `doctor_ok` (boolean)
- `evidence_window_end` (date)

## Compatibility rules

1. Consumers MUST ignore unknown fields.
2. Producers MUST keep required fields stable within a major version.
3. Additive changes SHOULD be released as minor versions.
4. Breaking changes MUST ship with dual-write period notes and migration examples.

## Migration process

1. Propose change and classify bump type (major/minor/patch).
2. Update this document and changelog entry in the same PR.
3. If major bump, publish migration snippet and dual-write duration.
4. Update dashboard references and executive template fields if impacted.

## Changelog

## 1.0.0 — 2026-04-15

- Initial schema versioning convention created.
- Defines required fields for portfolio rollups and risk-tier reporting.
