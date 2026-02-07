# Contributing

Thanks for helping improve sdetkit.

## Setup

```bash
cd ~/sdet_bootcamp
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .
```

## Quality gates (same as CI)

```bash
bash scripts/check.sh all
```

Individual steps:

```bash
bash scripts/check.sh fmt
bash scripts/check.sh lint
bash scripts/check.sh types
bash scripts/check.sh tests
bash scripts/check.sh coverage
bash scripts/check.sh docs
```

## Making changes

- Prefer small PRs with clear intent.
- Add/extend tests for behavior changes.
- Keep types clean (mypy passes).
- Keep formatting/lint clean (ruff passes).

## PR checklist

- [ ] `bash scripts/check.sh all` is green locally
- [ ] Tests added/updated for the change
- [ ] Docs updated if the CLI/API changed
- [ ] PR description includes what/why + how to verify
