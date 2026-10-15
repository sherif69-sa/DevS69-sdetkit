# GitHub Action: SDETKit gate

The repository is a GitHub Action. One step runs `sdetkit gate fast` on every pull request. It puts the verdict in the job summary, posts it as one comment on the pull request (updated on each push), and fails the job on `NO_SHIP` or `NOT_RUN`.

```yaml
name: SDETKit gate

on: pull_request

permissions:
  contents: read
  pull-requests: write # for the pull request comment

jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -e ".[test]" # however your project installs its tests' dependencies
      - uses: sherif69-sa/DevS69-sdetkit@v2.0.0
```

!!! note "Before 2.0.0 is tagged"
    The action ships with 2.0.0. Until the `v2.0.0` tag exists, use `@main`, or pin a commit SHA from `main`.

For repository hygiene findings in GitHub code scanning (governance files, configuration), see the [repo audit action](github-action.md#which-action-do-i-use).

## What it reports

The job summary and the comment show the same Markdown, which `python -m sdetkit gate fast --summary-out <file>` also writes locally:

```markdown
### :x: SDETKit gate fast: NO_SHIP

A check failed.

| Step | Result | Time |
| --- | --- | --- |
| `ruff` | :white_check_mark: passed | 0.1s |
| `mypy` | :white_check_mark: passed | 2.3s |
| `pytest` | :x: failed (exit 1) | 9.8s |

**First failure (test):** `FAILED tests/test_api.py::test_timeout` in `tests/test_api.py`

**Next:** `python -m pytest -q tests/test_api.py -o addopts=`

Checks ran with `/opt/hostedtoolcache/Python/3.12.7/x64/bin/python` (--python). Nothing was applied, merged or dismissed.
```

The action reads, runs and reports. It never changes, merges or approves anything.

## Which environment runs the checks

sdetkit is installed in its own virtual environment, so it never changes your project's dependencies. Your repository's ruff, mypy and pytest run in your project's environment:

1. the `python` input, when you set it;
2. otherwise the repository's `.venv` or `venv`, or Poetry's or Pipenv's environment (create it in an earlier step, for example with `uv sync` or `poetry install`);
3. otherwise the `python` on `PATH`: the one `actions/setup-python` set up and your earlier steps installed the project into.

When the project is not installed where the checks run, the verdict is `NOT_RUN` and the summary gives the setup command, instead of a `NO_SHIP` for code that may be fine. See [which Python runs the checks](configuration.md#which-python-runs-the-checks).

## Inputs

| Input | Default | Effect |
| --- | --- | --- |
| `working-directory` | `.` | Repository root to check. |
| `args` | | Extra arguments for `sdetkit gate fast`, for example `--only ruff,pytest` or `--skip mypy`. |
| `python` | | Interpreter for the repository's checks (see above). |
| `fail-on` | `NO_SHIP,NOT_RUN` | Verdicts that fail the step, comma-separated (`NO_SHIP`, `NOT_RUN`, `REVIEW`), or `none`. |
| `comment` | `true` | Post the summary as one pull request comment and update it on each run. |
| `sdetkit-version` | | Install this version from PyPI instead of the action's own source. |
| `github-token` | `github.token` | Token for the comment. |

## Outputs

| Output | Value |
| --- | --- |
| `verdict` | `SHIP`, `REVIEW`, `NOT_RUN` or `NO_SHIP`. |
| `report` | Path of the gate's JSON report; the verdict is under `verdict` ([artifact reference](artifact-reference.md)). |
| `summary` | Path of the Markdown summary. |

To keep the report, upload it in a later step:

```yaml
      - uses: sherif69-sa/DevS69-sdetkit@v2.0.0
        id: gate
      - if: always()
        uses: actions/upload-artifact@v4
        with:
          name: sdetkit-gate
          path: ${{ steps.gate.outputs.report }}
```

## Pull requests from forks

A pull request from a fork gets a read-only token, so the action cannot comment. It prints a warning and the job summary still has the verdict. Do not switch to `pull_request_target` to get a write token: it would run the fork's code with that token.

## Several projects in one repository

Run the action once per project with its `working-directory`. Each project gets its own comment.
