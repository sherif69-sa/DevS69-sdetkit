# Project structure

## Top level

- `src/sdetkit/` : library + CLI implementation
- `tests/` : test suite (includes mutation-test killers)
- `scripts/` : local developer commands (mirrors CI)
- `docs/` : mkdocs site pages
- `.github/` : CI workflows + templates

## Key modules

- `sdetkit/cli.py` : CLI router
- `sdetkit/_entrypoints.py` : console scripts (`kvcli`, `apigetcli`)
- `sdetkit/__main__.py` : `python -m sdetkit`
- `sdetkit/apiclient.py` : high-level request helpers
- `sdetkit/netclient.py` : advanced client behaviors (hooks/breaker/pagination)
- `sdetkit/atomicio.py` : safe/atomic file IO helpers
- `sdetkit/textutil.py` : small text utilities

## Scripts

- `scripts/check.sh` : fmt/lint/types/tests/coverage/docs/all
- `scripts/env.sh` : source this to put `.venv/bin` on PATH
- `scripts/shell.sh` : open an interactive shell with `.venv/bin` on PATH
