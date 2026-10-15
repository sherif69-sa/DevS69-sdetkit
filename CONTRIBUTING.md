# Contributing to DevS69 SDETKit

Thank you for your interest in improving SDETKit. Bug reports, documentation fixes, tests and code changes are all welcome. This guide covers how to set up a development environment, the checks a change has to pass, and how pull requests are reviewed.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md). To report a security vulnerability, follow the [Security Policy](SECURITY.md) instead of opening an issue.

## Contents

- [Ways to contribute](#ways-to-contribute)
- [Development setup](#development-setup)
- [Making a change](#making-a-change)
- [Validating your change](#validating-your-change)
- [Submitting a pull request](#submitting-a-pull-request)
- [Dependencies and lockfiles](#dependencies-and-lockfiles)
- [Repository automation secrets](#repository-automation-secrets)

## Ways to contribute

- **Report a bug.** Use the [bug report form](https://github.com/sherif69-sa/DevS69-sdetkit/issues/new/choose). Attach `build/gate-fast.json`, `build/release-preflight.json` and the output of `python -m sdetkit doctor` when you can; [SUPPORT.md](SUPPORT.md) lists what helps triage.
- **Propose a feature.** Use the feature request form and describe the problem before the solution.
- **Improve the docs.** Clarify wording, fix examples that drift from the CLI, or repair broken links in `docs/` and `README.md`.
- **Add tests** for existing behavior under `tests/`.
- **Fix an issue.** Issues labelled `good first issue` are scoped to one area with clear acceptance criteria; `help wanted` issues may need more context.

### Good first contributions

For a first pull request, prefer documentation, targeted tests, or lint and type fixes that do not change behavior. Changes to the CLI's command surface, the feature registry, or cross-cutting refactors need more context; please open an issue to discuss them first. [docs/starter-work-inventory.md](docs/starter-work-inventory.md) lists concrete starting points, and [docs/first-contribution-quickstart.md](docs/first-contribution-quickstart.md) is a condensed version of this guide.

## Development setup

SDETKit supports Python 3.10 and newer.

```bash
git clone https://github.com/<your-username>/DevS69-sdetkit.git
cd DevS69-sdetkit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev,test,docs]
pre-commit install
```

Alternatively, `make install` creates `.venv` and installs the package with the pinned test and documentation requirements; `make help` lists the other developer targets. [docs/project-structure.md](docs/project-structure.md) explains where files belong.

## Making a change

1. Create a branch from `main`, named for the change: `fix/<topic>`, `feat/<topic>` or `docs/<topic>`.
2. Keep the change focused: one concern per pull request is far easier to review.
3. Add or update tests for any behavior change. The test suite fails if a test modifies a tracked file, so write test output to temporary directories.
4. Update the documentation when you change commands, options or output.
5. Add an entry under `## Unreleased` in [CHANGELOG.md](CHANGELOG.md) for user-visible changes.

### Changes to the command surface

If your change adds or renames a top-level command, changes its tier or stability, or changes command examples, update the feature registry in the same pull request:

```bash
# after editing src/sdetkit/data/feature_registry.json
python scripts/sync_feature_registry_docs.py
python scripts/sync_feature_registry_docs.py --check
python -m pytest -q tests/test_feature_registry.py -o addopts=
```

### Commit messages

Write commit messages that say what changed and why, in the imperative mood ("Fix lockfile detection for Pipenv", not "Fixed stuff"). Reference the issue a commit resolves.

## Validating your change

Run the same checks CI runs before you open a pull request:

```bash
python -m pre_commit run -a        # ruff, ruff format, mypy and file hygiene
bash quality.sh cov                # tests with the coverage gate
mkdocs build                       # documentation
```

For changes that affect packaging, also run:

```bash
python -m build
python -m twine check dist/*
```

For documentation-only changes, `python -m pre_commit run -a` and `mkdocs build` are enough.

SDETKit should pass its own release-confidence path. Run it on your branch and check the verdict:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

`quality.sh cov` uses `COV_MODE=standard` (coverage must be at least 85%). `COV_MODE=strict` (95%) is the merge and release bar, and `COV_MODE=legacy` (80%) remains available during migration.

## Submitting a pull request

1. Push your branch and open a pull request against `main`.
2. Fill in the [pull request template](.github/PULL_REQUEST_TEMPLATE.md): what changed and why, the risk, how you tested it, and how to roll it back.
3. Make sure CI is green. The required checks are `ci` and `maintenance-autopilot`.
4. A maintainer reviews every pull request. Expect questions or requests for changes; push follow-up commits to the same branch rather than opening a new pull request.

Before requesting review, check that:

- [ ] `python -m pre_commit run -a` passes.
- [ ] `bash quality.sh cov` passes, or the pull request explains why it was not run.
- [ ] `python -m build` and `python -m twine check dist/*` pass for packaging changes.
- [ ] `mkdocs build` passes for documentation changes.
- [ ] `CHANGELOG.md` is updated for user-visible changes.

## Dependencies and lockfiles

`uv.lock` pins the full dependency tree of `pyproject.toml`. After changing a dependency in `pyproject.toml` or a pin in `constraints-ci.txt`, refresh it and commit the result:

```bash
make lock
```

`make lock` also sets the ruff and mypy hook revs in `.pre-commit-config.yaml` to their pins (`scripts/sync_pre_commit_revs.py`). CI fails when `uv.lock` no longer matches `pyproject.toml` or disagrees with `constraints-ci.txt`.

Dependabot's pip updates change `pyproject.toml` and `constraints-ci.txt` but not `uv.lock` or the hook revs. The `refresh-lock` job in `.github/workflows/dependency-auto-merge.yml` runs the same refresh on those pull requests and pushes both files. Dependabot stops rebasing a pull request once someone else has pushed to it; comment `@dependabot recreate` to start it over.

## Repository automation secrets

Maintainers configure two optional tokens. A push or pull request made with a workflow's own `GITHUB_TOKEN` does not start CI, so these workflows use their own token when it is present.

| Secret | Where to store it | Permissions | Used by |
| --- | --- | --- | --- |
| `DEPENDENCY_LOCK_TOKEN` | Settings → Secrets and variables → **Dependabot** | Contents: read and write | `refresh-lock` in `dependency-auto-merge.yml`, which pushes refreshed lockfiles to Dependabot pull requests |
| `PRE_COMMIT_AUTOUPDATE_TOKEN` | Settings → Secrets and variables → **Actions** | Contents and Pull requests: read and write | `pre-commit-autoupdate.yml`, which opens the weekly `pre-commit-hooks` update |

Use a fine-grained personal access token or a GitHub App installation token scoped to this repository. Workflows that Dependabot triggers can only read Dependabot secrets. Without `DEPENDENCY_LOCK_TOKEN`, the `refresh-lock` job comments with the command to run instead; without `PRE_COMMIT_AUTOUPDATE_TOKEN`, the autoupdate pull request still opens, with a warning that CI will not run. The ruff and mypy hook revs are not autoupdated: they follow their pins in `constraints-ci.txt`.

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE), the license of this project.
