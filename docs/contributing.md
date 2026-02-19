# Contributing

Use the repository root guide (`CONTRIBUTING.md`) for the full contributor workflow.

## Day 10 first-contribution checklist

Generate a guided checklist from clone to PR:

```bash
sdetkit first-contribution --format text --strict
sdetkit first-contribution --write-defaults --format json --strict
sdetkit first-contribution --format markdown --output docs/artifacts/day10-first-contribution-checklist-sample.md
```

Quick start:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev,test,docs]
pre-commit install
pre-commit run -a
bash quality.sh cov
mkdocs build
```
