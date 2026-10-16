# GitLab CI

One job, `sdetkit-gate`, runs `sdetkit gate fast` on merge requests and on the default branch. The job fails unless the gate passes, prints the verdict in the job log, and keeps the report as job artifacts, linked from the merge request as "SDETKit gate".

## Add the job

Include the template from a release tag in your `.gitlab-ci.yml`:

```yaml
include:
  - remote: https://raw.githubusercontent.com/sherif69-sa/DevS69-sdetkit/v2.0.0/examples/adoption/gitlab/sdetkit-gate.gitlab-ci.yml
```

Or copy [`examples/adoption/gitlab/sdetkit-gate.gitlab-ci.yml`](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/examples/adoption/gitlab/sdetkit-gate.gitlab-ci.yml) into your `.gitlab-ci.yml`. The job runs in the `test` stage on `python:3.12`.

## Set up your project

The gate runs ruff, mypy and pytest in your project's environment, so the job installs your project first. The template's `before_script` runs `python -m pip install -e ".[test]"` when the repository has a `pyproject.toml` or `setup.py`. When your project needs something else, override `before_script` in your `.gitlab-ci.yml`:

```yaml
sdetkit-gate:
  before_script:
    - python -m pip install -r requirements-dev.txt -e .
```

The gate uses the repository's `.venv` or `venv` (what `uv sync` creates), Poetry's or Pipenv's environment when there is one, and otherwise the job's `python`, where `before_script` installed the project.

When the environment is missing something, the gate reports `NOT_RUN` with `classification: environment` and the command that sets it up, not a test failure.

## Options

Set these under `variables:` in the `sdetkit-gate` job:

| Variable | Default | Use |
| --- | --- | --- |
| `SDETKIT_PACKAGE` | `sdetkit==2.0.0` | What pip installs: a version pin, or a git URL to try an unreleased change. |
| `SDETKIT_ARGS` | empty | Extra `gate fast` options separated by spaces, for example `--skip mypy` or `--only ruff,pytest`. |

## What the job does

1. `before_script`: installs your project.
2. Creates a virtual environment in a temporary directory and installs `$SDETKIT_PACKAGE` in it, so SDETKit never changes your project's dependencies.
3. Runs `gate fast --format json --stable-json --out build/sdetkit/gate.json --summary-out build/sdetkit/gate.md`, with `--python` set to the job's `python` when the repository has no environment of its own.
4. `after_script`: prints `build/sdetkit/gate.md`, the verdict, the step table, the first failure and the next command.
5. Keeps `build/sdetkit/` as artifacts, also when the job fails.

The job fails when `gate fast` exits non-zero: a check failed (`NO_SHIP`) or could not run (`NOT_RUN` with an environment problem). It does not comment on the merge request.

## How it is tested

CI's `CI templates (self)` job runs this job's `before_script` and `script` on a project whose tests pass (`SHIP`, exit 0) and one whose test fails (`NO_SHIP`, the job fails), with SDETKit installed from the checkout. `tests/test_ci_pipeline_templates.py` also checks the job's keywords, that `SDETKIT_PACKAGE` pins the current release, and that every step parses as shell.
