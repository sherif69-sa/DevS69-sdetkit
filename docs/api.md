# API

## HTTP serve API (`python -m sdetkit serve`)

- `GET /healthz`
- `POST /v1/review`
- `GET /v1/observability`

`/v1/observability` v2 fields include:

- `captured_at` (UTC timestamp)
- `observability_contract_version` (`2`)
- `freshness_summary` (present/missing/invalid_json/stale/fresh counts)
- per artifact:
  - `artifact_mtime`
  - `freshness_age_seconds`
  - `stale`
  - `stale_threshold_seconds`

Stale thresholds are configurable:

- global: `SDETKIT_OBSERVABILITY_STALE_SECONDS`
- per-artifact: `SDETKIT_OBSERVABILITY_STALE_<ARTIFACT_KEY>_SECONDS`

Validate observability contract:

```bash
python scripts/check_observability_v2_contract.py --format json
```

## sdetkit.apiclient
- fetch_json_dict(...)
- fetch_json_dict_async(...)
- fetch_json_list(...)
- fetch_json_list_async(...)

## sdetkit.netclient
Advanced client with hooks/observability and breaker-style behavior (see tests).
