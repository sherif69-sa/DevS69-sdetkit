# sdetkit

[![quality](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/quality.yml/badge.svg)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/quality.yml)
[![pages](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/pages.yml/badge.svg)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/pages.yml)




Small utilities for SDET-style exercises:

- `sdetkit.kvcli`: CLI that reads key=value pairs from stdin / --text / --path and prints JSON.
- `sdetkit.atomicio`: atomic write helper.
- `sdetkit.apiclient`: tiny JSON fetch helpers (sync + async).
- `sdetkit.textutil`: parsing utilities.

Quality gates:
- pytest
- 100% line coverage
- mutmut (mutation testing)

## CLI

### apiget
Fetch JSON from an endpoint.

- Get a JSON object:
  - sdetkit apiget https://example.com/api --expect dict

- Get a JSON array:
  - sdetkit apiget https://example.com/items --expect list

- Pagination (Link: rel="next"):
  - sdetkit apiget https://example.com/items --expect list --paginate --max-pages 50

- Retries + 429 retry + timeout:
  - sdetkit apiget https://example.com/items --expect list --retries 3 --retry-429 --timeout 2

- Trace header:
  - sdetkit apiget https://example.com/items --expect list --trace-header X-Request-ID
