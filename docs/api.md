# API

## HTTP serve API (`python -m sdetkit serve`)

- `GET /healthz` (no token needed)
- `POST /v1/review`
- `GET /v1/observability`

Every request except `/healthz` needs `Authorization: Bearer <token>`. The server prints a fresh token when it starts; set `SDETKIT_SERVER_TOKEN` to choose it instead. The server listens on `127.0.0.1` and refuses requests addressed to other host names. Listening on any other interface needs `--allow-remote`. The [tool server](tool-server.md#safety-model) uses the same rules.

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


## sdetkit.apiclient
- fetch_json_dict(...)
- fetch_json_dict_async(...)
- fetch_json_list(...)
- fetch_json_list_async(...)

## sdetkit.netclient
Advanced client with hooks/observability and breaker-style behavior (see tests).
