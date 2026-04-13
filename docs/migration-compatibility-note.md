# Migration and backward compatibility note

## What changed

SDETKit now treats the canonical public/stable path as the first-time entry point:

- `python -m sdetkit gate fast`
- `python -m sdetkit gate release`
- `python -m sdetkit doctor`

Umbrella kits remain advanced but supported:

- `sdetkit kits ...`
- `sdetkit release ...`
- `sdetkit intelligence ...`
- `sdetkit integration ...`
- `sdetkit forensics ...`

Operational maturity v2 additions:

- `scripts/adoption_scorecard.py` now emits `schema_version: "2"` with weighted/graded dimensions while keeping compatibility fields.
- `GET /v1/observability` now includes freshness metadata (`captured_at`, `artifact_mtime`, `freshness_age_seconds`, `stale`) and `observability_contract_version: "2"`.
- observability now also exposes a compact `freshness_summary` aggregate for dashboards.
- observability stale thresholds can now be tuned through environment variables without changing endpoint shape.
- `scripts/legacy_burndown.py` adds baseline-vs-current reduction KPI reporting from legacy analyzer output.

## What did not change

Stable direct commands remain supported and unchanged as compatibility lanes:

- `gate`, `doctor`, `security`, `repo`, `evidence`, `report`, `policy`

Backward compatibility specifics:

- scorecard consumers using `score`, `band`, and `dimensions` continue to work.
- observability endpoint route and top-level `contract_version` are unchanged.

## Practical migration guidance

- New scripts/docs: prefer kit routes.
- Existing CI scripts: no forced migration required.
- Gradual modernization: update discovery/help/docs first, then command paths over time.

## Experimental summary

Transition-era `dayNN-*` / `*-closeout` lanes remain available but are intentionally non-flagship.
Forensics remains production-usable with deterministic contracts while some sub-lanes may continue to evolve.
