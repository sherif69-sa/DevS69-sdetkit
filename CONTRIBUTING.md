<div align="center">

# Contributing

Thanks for helping improve **sdetkit**.

[README](README.md) · [Quality Playbook](QUALITY_PLAYBOOK.md) · [Security Policy](SECURITY.md) · [Live Docs](https://sherif69-sa.github.io/DevS69-sdetkit/)

</div>

---

## First trustworthy contribution

If this is your first PR to this repository, follow this safe-first path to make a small, high-confidence contribution without touching unstable surfaces.

### Safe starter surfaces (safe for first PR)

Start in one of these areas:

- **Docs clarification and cross-links** in `docs/` and `README.md` (wording, examples, broken internal links).
- **Small targeted tests** under `tests/` for existing behavior (no command-surface changes).
- **Lint/type hygiene fixes** that improve quality without changing behavior.
- **Contributor workflow polish** (guidance, issue/PR template clarity, validation instructions).

### Avoid first for your first PR (not forbidden forever)

For your first PR, avoid starting with these higher-risk surfaces:

- **Core CLI behavior/semantics** and top-level command-shape changes.
- **Feature registry/tier metadata updates** unless your issue explicitly requires them.
- **Broad command-family or cross-cutting refactors** that need deep architecture context.

These areas are important; they are just better as a second/third contribution after you are familiar with the repo.

### Issue -> change -> validation -> PR

1. **Pick a scoped issue**: prefer labels such as `good first issue`, `help wanted`, `documentation`, or `tests`.
2. **Make one focused change** in a safe starter surface.
3. **Run baseline validation**:
   ```bash
   python -m pre_commit run -a
   bash quality.sh cov
   mkdocs build
   ```
4. **Open your PR** using `.github/PULL_REQUEST_TEMPLATE.md` and include:
   - the issue you solved,
   - what changed,
   - commands you ran and outcomes.

### Canonical release-confidence alignment check

Before you open a PR, verify your docs/examples stay aligned with the canonical release-confidence path:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

Quick purpose guide (same order everywhere):
- `python -m sdetkit gate fast` — fast local quality gate signal before deeper checks.
- `python -m sdetkit gate release` — release-readiness preflight with machine-readable evidence.
- `python -m sdetkit doctor` — environment and diagnostics snapshot for troubleshooting context.

For a condensed version, see `docs/first-contribution-quickstart.md`.
For concrete, repo-grounded starter categories, use `docs/starter-work-inventory.md`.
For file-placement and root-directory guidance, see `docs/project-structure.md`.

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

Then pick a guided journey:

```bash
python -m sdetkit onboarding --journey first-pr --role sdet --format markdown
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

### Feature registry governance checklist

If your PR changes top-level commands, tier/stability, command examples, or command docs/test links, update the feature registry in one pass:

- [ ] Update `src/sdetkit/data/feature_registry.json`.
- [ ] Sync docs table: `python scripts/sync_feature_registry_docs.py`.
- [ ] Verify contract: `python scripts/check_feature_registry_contract.py`.
- [ ] Run maintenance lane: `bash quality.sh registry`.
- [ ] Confirm CLI inspector output remains stable: `python -m sdetkit feature-registry --only-core --format table`.

## Commit guidance

- Keep commits focused and easy to review.
- Include tests for behavior changes.
- Prefer typed public APIs and clear error messages.
- Write commit messages that describe **what changed** and **why**.

## PR quality tips (recommended)

- Add before/after snippets for docs UX changes.
- Mention affected commands/workflows.
- Keep PRs small enough for fast review turnaround.

## 0) First-contribution checklist

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
