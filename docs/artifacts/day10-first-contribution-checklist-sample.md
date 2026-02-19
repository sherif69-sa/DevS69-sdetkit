# Day 10 first-contribution checklist

- Score: **100.0** (14/14)
- Guide file: `CONTRIBUTING.md`

## Checklist

- [ ] Fork the repository and clone your fork locally.
- [ ] Create and activate a virtual environment.
- [ ] Install editable dependencies for dev/test/docs.
- [ ] Create a branch named `feat/<topic>` or `fix/<topic>`.
- [ ] Run focused tests for changed modules before committing.
- [ ] Run full quality gates (`pre-commit`, `quality.sh`, docs build) before opening a PR.
- [ ] Open a PR using the repository template and include test evidence.

## Required command sequence

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev,test,docs]
pre-commit run -a
bash quality.sh cov
mkdocs build
```

## Missing guide content

- none

## Actions

- `docs/contributing.md`
- `sdetkit first-contribution --format json --strict`
- `sdetkit first-contribution --write-defaults --strict`
- `sdetkit first-contribution --format markdown --output docs/artifacts/day10-first-contribution-checklist-sample.md`
