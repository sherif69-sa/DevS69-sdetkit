<div align="center">

# Contributing

Thanks for helping improve **sdetkit**.

[README](README.md) · [Quality Playbook](QUALITY_PLAYBOOK.md) · [Security Policy](SECURITY.md) · [Live Docs](https://sherif69-sa.github.io/DevS69-sdetkit/)

</div>

---

## 0) Day 10 first-contribution checklist

Use this guided path from local clone to first merged PR:

- [ ] Fork the repository and clone your fork locally.
- [ ] Create and activate a virtual environment.
- [ ] Install editable dependencies for dev/test/docs.
- [ ] Create a branch named `feat/<topic>` or `fix/<topic>`.
- [ ] Run focused tests for changed modules before committing.
- [ ] Run full quality gates (`pre-commit`, `quality.sh`, docs build) before opening a PR.
- [ ] Open a PR using the repository template and include test evidence.

Recommended shell sequence:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev,test,docs]
pre-commit run -a
bash quality.sh cov
mkdocs build
```

## Contribution flow

1. Fork and create a focused branch.
2. Implement changes with tests and documentation as needed.
3. Run local quality gates.
4. Open a pull request with clear context and impact.

## 1) Local development setup

```bash
cd ~/DevS69-sdetkit
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

Reference: [docs/premium-quality-gate.md](docs/premium-quality-gate.md)

- [ ] `pre-commit run -a` passes.
- [ ] `bash quality.sh cov` passes.
- [ ] `python -m build` and `python -m twine check dist/*` pass.
- [ ] `mkdocs build` passes for docs changes.
- [ ] `CHANGELOG.md` updated if behavior changed.

## 6) Commit guidance

- Keep commits focused and easy to review.
- Include tests for behavior changes.
- Prefer typed public APIs and clear error messages.
- Write commit messages that describe **what changed** and **why**.

## 7) PR quality tips (recommended)

- Add before/after snippets for docs UX changes.
- Mention affected commands/workflows.
- Keep PRs small enough for fast review turnaround.
