# Jenkins

A declarative pipeline with two stages, "Set up the project" and "SDETKit gate", runs `sdetkit gate fast`. The build fails unless the gate passes, the verdict is printed in the console log, and the report is archived.

## Add the pipeline

Copy `examples/adoption/jenkins/sdetkit-gate.Jenkinsfile` from this repository into your `Jenkinsfile`, or add its two stages and its `post` block to your pipeline. The agent needs `python3`; on a Docker-enabled agent, `agent { docker { image 'python:3.12' } }` works too.

## Set up your project

The gate runs ruff, mypy and pytest in your project's environment. The "Set up the project" stage creates `.venv` in the workspace and runs `.venv/bin/python -m pip install -e ".[test]"` when the repository has a `pyproject.toml` or `setup.py`. Replace it with your own setup when your project needs something else, such as `uv sync` or `poetry install`.

The gate uses the repository's `.venv` or `venv`, Poetry's or Pipenv's environment when there is one, and otherwise the agent's `python3`. When the environment is missing something, the gate reports `NOT_RUN` with `classification: environment` and the command that sets it up, not a test failure.

## Options

Set these in the `environment` block:

| Variable | Default | Use |
| --- | --- | --- |
| `SDETKIT_PACKAGE` | `sdetkit==2.0.0` | What pip installs: a version pin, or a git URL to try an unreleased change. |
| `SDETKIT_ARGS` | empty | Extra `gate fast` options separated by spaces, for example `--skip mypy` or `--only ruff,pytest`. |

## What the pipeline does

1. "Set up the project": creates `.venv` and installs your project in it.
2. "SDETKit gate": creates a virtual environment in a temporary directory, installs `$SDETKIT_PACKAGE` in it so SDETKit never changes your project's dependencies, and runs `gate fast --format json --stable-json --out build/sdetkit/gate.json --summary-out build/sdetkit/gate.md`.
3. `post { always }`: prints `build/sdetkit/gate.md` (the verdict, the step table, the first failure and the next command) and archives `build/sdetkit/**`.

The build fails when `gate fast` exits non-zero: a check failed (`NO_SHIP`) or could not run (`NOT_RUN` with an environment problem).

## How it is tested

CI's `CI templates (self)` job runs the pipeline's `sh` steps in order on a project whose tests pass (`SHIP`) and one whose test fails (`NO_SHIP`, the gate stage fails), with SDETKit installed from the checkout. `tests/test_ci_pipeline_templates.py` also checks that `SDETKIT_PACKAGE` pins the current release, that the archived path is where the gate writes, and that every step parses as shell.
