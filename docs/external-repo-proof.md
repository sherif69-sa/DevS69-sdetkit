# External repository proof

SDETKit's `gate fast`, run on well-known open-source Python projects at pinned commits. Each project is run twice: on a fresh clone, and again after the setup command SDETKit suggests for it. Every outcome is recorded as it came out, including the ones SDETKit gets wrong; the notes under each project say which is which.

Recorded on 2026-10-15 with SDETKit at commit `fddad3b9dc0d`, Python 3.13.16 on Linux x86_64, uv 0.11.32 (x86_64-unknown-linux-gnu), Poetry (version 2.4.3).

Run in a cloud sandbox whose network allows GitHub and the package indexes but not arbitrary hosts, so tests that open other connections fail there.

## Results

| Project | Commit | Fresh clone | Setup command | After setup |
| --- | --- | --- | --- | --- |
| [pallets/itsdangerous](https://github.com/pallets/itsdangerous) | `672971d66a2e` | **NOT_RUN** | `uv sync` | **SHIP** |
| [pallets/markupsafe](https://github.com/pallets/markupsafe) | `4e111271b149` | **NOT_RUN** | `uv sync` | **SHIP** |
| [pallets/click](https://github.com/pallets/click) | `2247b35ea1c4` | **NO_SHIP** | `uv sync` | **SHIP** |
| [python-attrs/attrs](https://github.com/python-attrs/attrs) | `ee66e7274852` | **NO_SHIP** | `uv sync` | **NO_SHIP** |
| [pytest-dev/pluggy](https://github.com/pytest-dev/pluggy) | `21c7e1672941` | **NOT_RUN** | `uv sync` | **SHIP** |
| [python-poetry/poetry-core](https://github.com/python-poetry/poetry-core) | `b52c25c451bb` | **NO_SHIP** | `poetry install` | **SHIP** |
| [psf/requests](https://github.com/psf/requests) | `611c6162cbc4` | **NO_SHIP** | `python -m venv .venv && .venv/bin/python -m pip install -e .` | **NO_SHIP** |

`NOT_RUN` means the checks could not run against the repository, and the next command says how to fix that. `NO_SHIP` means a check failed.

## Gaps this proof found in SDETKit

- pallets/click: Fresh clone: NO_SHIP is wrong. The tests imported the click release installed next to SDETKit, not this checkout, and SDETKit does not notice.
- python-attrs/attrs: mypy NO_SHIP is wrong. attrs configures mypy without `files` and type-checks only its `.pyi` stubs (tox `mypy` env); SDETKit falls back to `mypy src`, which the project never runs.
- python-attrs/attrs: Fresh clone: NO_SHIP is wrong. The tests imported the attrs release installed next to SDETKit, without the project's test dependencies.
- python-poetry/poetry-core: Fresh clone: NO_SHIP is wrong. mypy could not find `tomli_w`, a dependency that is not installed next to SDETKit.
- psf/requests: Fresh clone: the pytest failure is wrong. The tests imported the requests release installed next to SDETKit, and 205 errored for want of the project's test dependencies.
- psf/requests: ruff_format NO_SHIP is wrong. requests excludes `tests/test_lowlevel.py` from its pre-commit `ruff-format` hook; SDETKit checks the file anyway.
- psf/requests: The suggested setup installs the package but not `requirements-dev.txt`, so the project environment has no pytest and the tests do not run.

## Per project

### pallets/itsdangerous

Commit [`672971d66a2e`](https://github.com/pallets/itsdangerous/tree/672971d66a2ef9f85151e53283113f33d642dabd), lockfiles: `uv.lock`, setup: `uv sync` (exit 0).

- **Fresh clone:** NOT_RUN (exit 2, 5s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ❌.
  - First failure (environment): `pytest could not import this project's own package 'itsdangerous': the project is not installed in the interpreter the tests ran with (/usr/bin/python)`
  - Next command: `uv sync && python -m sdetkit gate fast`
- **After setup:** SHIP (exit 0, 8s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ✅.

- Right: Fresh clone: NOT_RUN is right. The src-layout package is not installed yet.
- Right: After `uv sync`: SHIP from the project's own ruff, mypy and pytest.

### pallets/markupsafe

Commit [`4e111271b149`](https://github.com/pallets/markupsafe/tree/4e111271b1494995708a9e878a10829b5e10c7ba), lockfiles: `uv.lock`, setup: `uv sync` (exit 0).

- **Fresh clone:** NOT_RUN (exit 2, 4s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ❌, pytest ✅.
  - First failure (environment): `mypy reported errors only in installed packages, not in this repository (/usr/local/lib/python3.13/dist-packages/numpy/__init__.pyi): it is reading an environment that is not the project's`
  - Next command: `uv sync && python -m sdetkit gate fast`
- **After setup:** SHIP (exit 0, 10s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ✅.

- Right: Fresh clone: NOT_RUN is right. mypy failed only inside numpy stubs installed next to SDETKit, not in this repository.
- Right: After `uv sync`: SHIP, with the tests importing the checkout.

### pallets/click

Commit [`2247b35ea1c4`](https://github.com/pallets/click/tree/2247b35ea1c47c727d7a06e51fa280e12a863ff6), lockfiles: `uv.lock`, setup: `uv sync` (exit 0).

- **Fresh clone:** NO_SHIP (exit 2, 17s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ❌.
  - First failure (test): `FAILED tests/test_abort_interrupt.py::test_interrupt_while_reporting_abort[prompt-1]`
  - Next command: `PYTHONPATH=src python -m pytest -q tests/test_abort_interrupt.py::test_interrupt_while_reporting_abort[prompt-1] -o addopts=`
- **After setup:** SHIP (exit 0, 14s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ✅.

- SDETKit gap: Fresh clone: NO_SHIP is wrong. The tests imported the click release installed next to SDETKit, not this checkout, and SDETKit does not notice.
- Right: After `uv sync`: SHIP.

### python-attrs/attrs

Commit [`ee66e7274852`](https://github.com/python-attrs/attrs/tree/ee66e7274852438cc23d4240a1a9cd632fda8b52), lockfiles: `uv.lock`, setup: `uv sync` (exit 0).

- **Fresh clone:** NO_SHIP (exit 2, 5s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ❌, pytest ❌.
  - First failure (type): `src/attr/_config.py:8: error: Function is missing a type annotation`
  - Next command: `python -m mypy src`
- **After setup:** NO_SHIP (exit 2, 23s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ❌, pytest ❌.
  - First failure (type): `src/attr/_config.py:8: error: Function is missing a type annotation`
  - Next command: `python -m mypy src`

- SDETKit gap: mypy NO_SHIP is wrong. attrs configures mypy without `files` and type-checks only its `.pyi` stubs (tox `mypy` env); SDETKit falls back to `mypy src`, which the project never runs.
- SDETKit gap: Fresh clone: NO_SHIP is wrong. The tests imported the attrs release installed next to SDETKit, without the project's test dependencies.
- Right: After `uv sync`: the pytest failures are the project's own in this environment (a pyright baseline test that depends on the pyright version).

### pytest-dev/pluggy

Commit [`21c7e1672941`](https://github.com/pytest-dev/pluggy/tree/21c7e1672941a0cd9e3c555bf5e5007f1fbe3dc5), lockfiles: `uv.lock`, setup: `uv sync` (exit 0).

- **Fresh clone:** NOT_RUN (exit 2, 6s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ❌.
  - First failure (environment): `pytest could not import this project's own package 'pluggy': the project is not installed in the interpreter the tests ran with (/usr/bin/python)`
  - Next command: `uv sync && python -m sdetkit gate fast`
- **After setup:** SHIP (exit 0, 3s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ✅.

- Right: Fresh clone: NOT_RUN is right. pluggy is not installed yet.
- Right: After `uv sync`: SHIP.

### python-poetry/poetry-core

Commit [`b52c25c451bb`](https://github.com/python-poetry/poetry-core/tree/b52c25c451bbaed9f309d45fc6e6e35c704e55bf), lockfiles: `poetry.lock`, setup: `poetry install` (exit 0).

- **Fresh clone:** NO_SHIP (exit 2, 15s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ❌, pytest ❌.
  - First failure (type): `tests/testutils.py:14: error: Cannot find implementation or library stub for module named "tomli_w" [import-not-found]`
  - Next command: `python -m mypy src`
- **After setup:** SHIP (exit 0, 42s, python from `poetry`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ✅.

- SDETKit gap: Fresh clone: NO_SHIP is wrong. mypy could not find `tomli_w`, a dependency that is not installed next to SDETKit.
- Right: After `poetry install`: SHIP, found through `poetry env info` (Poetry keeps the environment outside the repository).

### psf/requests

Commit [`611c6162cbc4`](https://github.com/psf/requests/tree/611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60), lockfiles: none, setup: `python -m venv .venv && .venv/bin/python -m pip install -e .` (exit 0).

- **Fresh clone:** NO_SHIP (exit 2, 47s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ❌, pytest ❌.
  - First failure (formatter_only): `unformatted: File would be reformatted`
  - Next command: `python -m ruff format --check tests/test_lowlevel.py`
- **After setup:** NO_SHIP (exit 2, 2s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ❌, pytest ❌.
  - First failure (formatter_only): `unformatted: File would be reformatted`
  - Next command: `python -m ruff format --check tests/test_lowlevel.py`

- SDETKit gap: Fresh clone: the pytest failure is wrong. The tests imported the requests release installed next to SDETKit, and 205 errored for want of the project's test dependencies.
- SDETKit gap: ruff_format NO_SHIP is wrong. requests excludes `tests/test_lowlevel.py` from its pre-commit `ruff-format` hook; SDETKit checks the file anyway.
- SDETKit gap: The suggested setup installs the package but not `requirements-dev.txt`, so the project environment has no pytest and the tests do not run.

## Reproduce

```bash
python scripts/external_repo_proof.py run --workdir /tmp/external-repos
python scripts/external_repo_proof.py render
```

`run` needs network access to GitHub and the package indexes, plus `uv` and `poetry` on `PATH`, and rewrites `docs/artifacts/external-repo-proof/results.json`; `render` rebuilds this page from it. A test keeps the page and the results in step.
