# First contribution checklist report

- Score: **94.4** (17/18)
- Guide file: `CONTRIBUTING.md`
- Selected starter profile: `all`
- Recommended starter profile: `docs-polish`

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

## Starter profiles

### Docs polish (`docs-polish`)

- Impact: Clarify commands, fix internal links, and improve first-run confidence.
- Good starter files: `README.md`, `docs/choose-your-path.md`, `CONTRIBUTING.md`
- Validate with: `python -m pre_commit run -a`, `mkdocs build`
- First steps:
  - Read README.md and docs/choose-your-path.md to find wording drift or broken handoffs.
  - Make one focused docs update that shortens the path from landing page to first successful command.
  - Run docs-safe validation before opening your PR.

### Test hardening (`test-hardening`)

- Impact: Add focused regression coverage without changing the public surface area.
- Good starter files: `tests/`, `src/sdetkit/`
- Validate with: `python -m pytest -q`, `bash quality.sh cov`
- First steps:
  - Pick one documented CLI behavior and find the closest existing test module.
  - Add one regression or edge-case assertion without broad refactors.
  - Run the focused test file first, then the repo quality gate if scope grows.

### Automation upgrade (`automation-upgrade`)

- Impact: Improve CI repeatability, artifact quality, or release safety checks.
- Good starter files: `scripts/`, `templates/automations/`, `.github/`
- Validate with: `python -m pre_commit run -a`, `bash quality.sh cov`, `python -m build`
- First steps:
  - Inspect one automation path with a clear before/after improvement opportunity.
  - Keep the change scoped to one workflow or template family.
  - Validate both local quality checks and packaging/build safety when relevant.

## Contributor trust assets

- [x] `docs/starter-work-inventory.md` - Starter work inventory: Gives first-time contributors concrete, repo-specific starter lanes.
- [x] `docs/first-contribution-quickstart.md` - First contribution quickstart: Provides a short path from clone to reviewable PR.
- [x] `.github/PULL_REQUEST_TEMPLATE.md` - PR template: Sets reviewer expectations and keeps contribution evidence consistent.
- [x] `.github/ISSUE_TEMPLATE/feature_request.yml` - Feature request template: Lets new contributors propose scoped work without guessing the maintainer format.

## Guide coverage gaps

- `## 0) First-contribution checklist`

## Missing trust assets

- none

## Good-first-issue labels

- `good first issue`
- `help wanted`
- `documentation`
- `tests`
- `needs-triage`

## Actions

- Open guide: `CONTRIBUTING.md`
- Validate: `sdetkit first-contribution --format json --strict`
- Spotlight docs profile: `sdetkit first-contribution --profile docs-polish --format markdown`
- Spotlight test profile: `sdetkit first-contribution --profile test-hardening --format markdown`
- Spotlight automation profile: `sdetkit first-contribution --profile automation-upgrade --format markdown`
- Write defaults: `sdetkit first-contribution --write-defaults --strict`
- Export artifact: `sdetkit first-contribution --format markdown --output docs/artifacts/first-contribution-checklist-sample.md`
