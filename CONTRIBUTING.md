<div align="center">

# Contributing

Thanks for helping improve **sdetkit**.

[README](README.md) · [Quality Playbook](QUALITY_PLAYBOOK.md) · [Security Policy](SECURITY.md) · [Live Docs](https://sherif69-sa.github.io/DevS69-sdetkit/)

</div>

---

## Start here (first external contribution)

If this is your first PR to this repository, use this shortest safe path:

1. **Set up locally**
   ```bash
   bash scripts/bootstrap.sh
   source .venv/bin/activate
   ```
2. **Choose one small contribution type** from [Starter contribution types](#starter-contribution-types).
3. **Make one focused change** and keep the PR scope small.
4. **Validate before push**:
   ```bash
   python -m pre_commit run -a
   bash quality.sh cov
   ```
5. **Open a PR** using `.github/PULL_REQUEST_TEMPLATE.md` and include the commands you ran.

For a condensed version, see `docs/first-contribution-quickstart.md`.
For concrete, repo-grounded starter categories, use `docs/starter-work-inventory.md`.

## Starter contribution types

Use these when you want a realistic first PR without deep project context:

- **Docs/example improvements**: clarify command wording, tighten examples, or fix broken internal doc links in `docs/` and `README.md`.
- **Small tests**: add or extend targeted tests under `tests/` for existing CLI behavior.
- **Lint/type hygiene fixes**: fix Ruff or mypy findings without changing behavior.
- **Workflow/docs polish**: improve contributor/developer docs or issue-template clarity.
- **CLI/docs alignment**: update docs when command names/options drift from actual CLI output.

If you are unsure where to start, run:

```bash
python -m sdetkit first-contribution --format text --strict
```

## Where to find starter work

- Look for open issues labelled **`good first issue`**, **`help wanted`**, **`documentation`**, **`tests`**, or **`needs-triage`**.
- If no issue fits, pick a safe path from `docs/starter-work-inventory.md`.
- Open a small scoped feature request (use `.github/ISSUE_TEMPLATE/feature_request.yml`) and mark it as first-contribution sized.
- Prefer changes that can be reviewed in one pass and validated with existing commands.

### Starter-label expectations

- **`good first issue`**: scoped to one workflow/file group, clear acceptance criteria, no deep architecture context required.
- **`help wanted`**: useful but may require more context; still includes explicit acceptance criteria.
- **`documentation` / `tests`**: indicate domain so contributors can filter by skill.
- **`needs-triage`**: intake state only; move to specific labels after maintainers confirm scope.

## Local development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev,test,docs]
```

## Enable pre-commit hooks

```bash
pre-commit install
python -m ruff format --check .
python -m pre_commit run -a
```

## Validate changes before opening a PR

Use the same commands expected by CI:

```bash
python -m ruff format --check .
python -m pre_commit run -a
bash quality.sh cov
python -m build
python -m twine check dist/*
mkdocs build
```

For docs-only updates, run at least:

```bash
python -m pre_commit run -a
mkdocs build
```

## Pull request checklist

Reference: [docs/premium-quality-gate.md](docs/premium-quality-gate.md)

- [ ] `python -m pre_commit run -a` passes.
- [ ] `bash quality.sh cov` passes (or explain why not run).
- [ ] `python -m build` and `python -m twine check dist/*` pass for packaging-impacting changes.
- [ ] `mkdocs build` passes for docs changes.
- [ ] `CHANGELOG.md` updated if behavior changed.

## Commit guidance

- Keep commits focused and easy to review.
- Include tests for behavior changes.
- Prefer typed public APIs and clear error messages.
- Write commit messages that describe **what changed** and **why**.

## PR quality tips (recommended)

- Add before/after snippets for docs UX changes.
- Mention affected commands/workflows.
- Keep PRs small enough for fast review turnaround.
