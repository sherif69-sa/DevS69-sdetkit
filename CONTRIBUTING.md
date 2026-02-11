# Contributing

Thanks for helping improve `sdetkit`.

## 1) Local development setup

```bash
cd ~/sdet_bootcamp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev,test,docs]
```

## 2) Enable pre-commit hooks

```bash
pre-commit install
python -m ruff format --check .
python -m pre_commit run -a
```

## 3) Run quality gates locally

Use the same commands expected by CI:

```bash
python -m ruff format --check .
python -m pre_commit run -a
bash quality.sh cov
python -m build
python -m twine check dist/*
mkdocs build
```

## 4) Common day-to-day commands

```bash
ruff format .
ruff check .
mypy src
pytest -q
```

## 5) Pull request checklist

Premium reference: `docs/premium-quality-gate.md`


- [ ] `pre-commit run -a` passes.
- [ ] `bash quality.sh cov` passes.
- [ ] `python -m build` and `python -m twine check dist/*` pass.
- [ ] `mkdocs build` passes for docs changes.
- [ ] `CHANGELOG.md` updated if behavior changed.

## 6) Commit guidance

- Keep commits focused and easy to review.
- Include tests for behavior changes.
- Prefer typed public APIs and clear error messages.
