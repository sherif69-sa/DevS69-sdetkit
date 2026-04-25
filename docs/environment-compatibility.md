# Environment compatibility matrix

This is the execution baseline for the **first-proof** lane.

## Supported runtime

- Python: **3.10+ required**
- Recommended active versions: 3.10, 3.11, 3.12, 3.13
- Current known block: Python 3.9 and lower are not supported by `sdetkit`
- Contributor tooling note: runtime compatibility is 3.10+, while local lint/type-check parity is best on Python 3.12 (matching project `ruff`/`mypy` config in `pyproject.toml`).

## First-proof dependencies

- Virtual environment (`python -m venv .venv`)
- Editable install (`pip install -e .`)
- Test/docs dependencies for full local quality runs (`requirements-test.txt`, `requirements-docs.txt`)
- `scripts/first_proof.py` auto-selects a Python 3.10+ interpreter by default when available.
- `scripts/first_proof.py` defaults to non-strict exit behavior for local smoke runs; pass `--strict` (used by `make first-proof`) to enforce non-zero exit on gate failures.
- `scripts/check_first_proof_summary_contract.py` supports `--wait-seconds` for parallel pipelines where summary writing may still be in progress.
- For optional lanes where summary may not exist yet, use `--allow-missing` to return success with a JSON `skipped: true` record.
- The contract checker now retries not only missing/unreadable files, but also stale/partial contract content until the wait window expires.
- `make first-proof-verify` now also updates a first-proof learning DB and adaptive reviewer rollup for trend-based optimization.

## Quick remediation by symptom

For expanded failure signatures, see `docs/first-proof-troubleshooting.md`.

### Symptom: `sdetkit requires Python 3.10+`

Fix:

1. Install Python 3.10+.
2. Recreate the environment:

```bash
rm -rf .venv
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

### Symptom: first-proof commands fail after clone

Fix:

```bash
source .venv/bin/activate
python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .
make first-proof
```

## CI recommendation

Run first-proof in matrix mode for at least:

- Python 3.10
- Python 3.12
- Python 3.13

Keep `first-proof-summary.json` as a required artifact in every matrix leg.
