# First contribution quickstart

This page is for first-time external contributors who want a small, safe PR.

## 1) Local setup (fast path)

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
```

If you prefer manual setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev,test,docs]
```

## 2) Pick a realistic first contribution type

Use `docs/starter-work-inventory.md` for concrete categories mapped to this repo, then choose one:

1. **Docs/example polish** (`README.md`, `docs/`)
   - Clarify command wording.
   - Fix broken or confusing internal links.
   - Improve examples to match current CLI behavior.
2. **Targeted tests** (`tests/`)
   - Add one focused test for existing command behavior.
   - Extend an existing test file with an edge case.
3. **Lint/type small fixes** (`src/`, `tests/`)
   - Resolve Ruff/mypy findings without behavior changes.
4. **CLI/docs alignment**
   - Update docs when command names/options/output changed.

## 3) Validate locally before opening a PR

Run minimum checks:

```bash
python -m pre_commit run -a
bash quality.sh cov
```

For docs-only changes:

```bash
python -m pre_commit run -a
mkdocs build
```

## 4) Open your PR

- Use the PR template: `.github/PULL_REQUEST_TEMPLATE.md`.
- Include exact commands you ran and key output.
- Keep scope small so review can complete quickly.

## 5) Need help finding starter work?

- Search issues for labels like `good first issue`, `help wanted`, `documentation`, `tests`, and `needs-triage`.
- If nothing fits, choose a safe category from `docs/starter-work-inventory.md`.
- Open a scoped proposal with `.github/ISSUE_TEMPLATE/feature_request.yml` and mention it is your first contribution.

## Optional helper command

Generate the repository checklist:

```bash
python -m sdetkit first-contribution --format text --strict
```

For the complete workflow, see [Contributing](contributing.md).
