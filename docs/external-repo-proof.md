# External repository proof

SDETKit's `gate fast`, run on well-known open-source Python projects at pinned commits. Each project is run twice: on a fresh clone, and again after the setup command SDETKit suggests for it. Every outcome is recorded as it came out, including the ones SDETKit gets wrong; the notes under each project say which is which.

Recorded on 2026-10-15 with SDETKit at commit `a9fe9dfd8c6d`, Python 3.13.16 on Linux x86_64, uv 0.11.32 (x86_64-unknown-linux-gnu), Poetry (version 2.4.3).

Run in a cloud sandbox whose network allows GitHub and the package indexes but not arbitrary hosts, so tests that open other connections fail there.

## Results

| Project | Commit | Fresh clone | Setup command | After setup |
| --- | --- | --- | --- | --- |
| [pallets/itsdangerous](https://github.com/pallets/itsdangerous) | `672971d66a2e` | **NOT_RUN** | `uv sync` | **SHIP** |
| [pallets/markupsafe](https://github.com/pallets/markupsafe) | `4e111271b149` | **NOT_RUN** | `uv sync` | **SHIP** |
| [pallets/click](https://github.com/pallets/click) | `2247b35ea1c4` | **NOT_RUN** | `uv sync` | **SHIP** |
| [python-attrs/attrs](https://github.com/python-attrs/attrs) | `ee66e7274852` | **NOT_RUN** | `uv sync` | **NO_SHIP** |
| [pytest-dev/pluggy](https://github.com/pytest-dev/pluggy) | `21c7e1672941` | **NOT_RUN** | `uv sync` | **SHIP** |
| [python-poetry/poetry-core](https://github.com/python-poetry/poetry-core) | `b52c25c451bb` | **NOT_RUN** | `poetry install` | **SHIP** |
| [psf/requests](https://github.com/psf/requests) | `611c6162cbc4` | **NOT_RUN** | `python -m venv .venv && .venv/bin/python -m pip install -e . -r requirements-dev.txt` | **NO_SHIP** |

`NOT_RUN` means the checks could not run against the repository, and the next command says how to fix that. `NO_SHIP` means a check failed.

## Gaps this proof found in SDETKit

None open. Earlier runs of this proof found gaps that have since been fixed; `CHANGELOG.md` lists them.

## Per project

### pallets/itsdangerous

Commit [`672971d66a2e`](https://github.com/pallets/itsdangerous/tree/672971d66a2ef9f85151e53283113f33d642dabd), lockfiles: `uv.lock`, setup: `uv sync` (exit 0).

- **Fresh clone:** NOT_RUN (exit 2, 4s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ❌.
  - First failure (environment): `pytest could not import this project's own package 'itsdangerous': the project is not installed in the interpreter the tests ran with (/usr/bin/python)`
  - Next command: `uv sync && python -m sdetkit gate fast`
- **After setup:** SHIP (exit 0, 6s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ✅.

- Right: Fresh clone: NOT_RUN is right. The src-layout package is not installed yet.
- Right: After `uv sync`: SHIP from the project's own ruff, mypy and pytest.

### pallets/markupsafe

Commit [`4e111271b149`](https://github.com/pallets/markupsafe/tree/4e111271b1494995708a9e878a10829b5e10c7ba), lockfiles: `uv.lock`, setup: `uv sync` (exit 0).

- **Fresh clone:** NOT_RUN (exit 2, 4s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ❌, pytest ✅.
  - First failure (environment): `mypy reported errors only in installed packages, not in this repository (/usr/local/lib/python3.13/dist-packages/numpy/__init__.pyi): it is reading an environment that is not the project's`
  - Next command: `uv sync && python -m sdetkit gate fast`
- **After setup:** SHIP (exit 0, 5s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ✅.

- Right: Fresh clone: NOT_RUN is right. mypy failed only inside numpy stubs installed next to SDETKit, not in this repository.
- Right: After `uv sync`: SHIP, with the tests importing the checkout.

### pallets/click

Commit [`2247b35ea1c4`](https://github.com/pallets/click/tree/2247b35ea1c47c727d7a06e51fa280e12a863ff6), lockfiles: `uv.lock`, setup: `uv sync` (exit 0).

- **Fresh clone:** NOT_RUN (exit 2, 21s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ❌.
  - First failure (environment): `the tests imported click 8.5.0 installed at /usr/local/lib/python3.13/dist-packages/click/__init__.py, not this checkout ('click' resolves outside the repository in /usr/bin/python)`
  - Next command: `uv sync && python -m sdetkit gate fast`
- **After setup:** SHIP (exit 0, 14s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ✅.

- Right: Fresh clone: NOT_RUN is right. The tests imported the click 8.5.0 release installed next to SDETKit, not this checkout, and the gate says so.
- Right: After `uv sync`: SHIP.

### python-attrs/attrs

Commit [`ee66e7274852`](https://github.com/python-attrs/attrs/tree/ee66e7274852438cc23d4240a1a9cd632fda8b52), lockfiles: `uv.lock`, setup: `uv sync` (exit 0).

- **Fresh clone:** NOT_RUN (exit 2, 6s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ❌.
  - First failure (environment): `pytest could not import 'cloudpickle': no project environment was found, so the tests ran with SDETKit's own interpreter (/usr/bin/python), which does not have the project's dependencies`
  - Next command: `uv sync && python -m sdetkit gate fast`
- **After setup:** NO_SHIP (exit 2, 23s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ❌.
  - First failure (test): `FAILED tests/test_pyright.py::test_pyright_baseline - assert {('error', 'C......`
  - Next command: `PYTHONPATH=src python -m pytest -q tests/test_pyright.py::test_pyright_baseline -o addopts=`

- Right: mypy runs attrs's own tox commands (`mypy typing_tests` and the `.pyi` stubs) and passes; attrs configures mypy without `files`.
- Right: Fresh clone: NOT_RUN is right. With no project environment, test dependencies such as `cloudpickle` are missing.
- Right: After `uv sync`: NO_SHIP is right in this environment. `tests/test_pyright.py::test_pyright_baseline` expects the output of another pyright version than the one installed; the other 1407 tests pass.

### pytest-dev/pluggy

Commit [`21c7e1672941`](https://github.com/pytest-dev/pluggy/tree/21c7e1672941a0cd9e3c555bf5e5007f1fbe3dc5), lockfiles: `uv.lock`, setup: `uv sync` (exit 0).

- **Fresh clone:** NOT_RUN (exit 2, 5s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ❌, pytest ❌.
  - First failure (environment): `mypy reported errors only in installed packages, not in this repository (/usr/local/lib/python3.13/dist-packages/numpy/__init__.pyi): it is reading an environment that is not the project's`
  - Next command: `uv sync && python -m sdetkit gate fast`
- **After setup:** SHIP (exit 0, 6s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ✅.

- Right: Fresh clone: NOT_RUN is right. pluggy is not installed yet, and mypy on its pre-commit hook's files failed only inside numpy stubs installed next to SDETKit.
- Right: After `uv sync`: SHIP, with mypy on the files its pre-commit hook selects (`src/` and `testing/`).

### python-poetry/poetry-core

Commit [`b52c25c451bb`](https://github.com/python-poetry/poetry-core/tree/b52c25c451bbaed9f309d45fc6e6e35c704e55bf), lockfiles: `poetry.lock`, setup: `poetry install` (exit 0).

- **Fresh clone:** NOT_RUN (exit 2, 13s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ❌, pytest ❌.
  - First failure (environment): `poetry-core is not installed in the interpreter the checks ran with (/usr/bin/python) and no project environment was found, so its dependencies are missing there`
  - Next command: `poetry install && python -m sdetkit gate fast`
- **After setup:** SHIP (exit 0, 43s, python from `poetry`). Steps: doctor ✅, ruff ✅, ruff_format ✅, mypy ✅, pytest ✅.

- Right: Fresh clone: NOT_RUN is right. poetry-core is not installed next to SDETKit, so its dependencies (such as `tomli_w`, which mypy looked for) are missing.
- Right: After `poetry install`: SHIP, found through `poetry env info` (Poetry keeps the environment outside the repository).

### psf/requests

Commit [`611c6162cbc4`](https://github.com/psf/requests/tree/611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60), lockfiles: none, setup: `python -m venv .venv && .venv/bin/python -m pip install -e . -r requirements-dev.txt` (exit 0).

- **Fresh clone:** NOT_RUN (exit 2, 47s, python from `sdetkit`). Steps: doctor ✅, ruff ✅, ruff_format ✅, pytest ❌.
  - First failure (environment): `the tests imported requests 2.34.2 installed at /root/.local/lib/python3.13/site-packages/requests/__init__.py, not this checkout ('requests' resolves outside the repository in /usr/bin/python)`
  - Next command: `python -m venv .venv && .venv/bin/python -m pip install -e . -r requirements-dev.txt && python -m sdetkit gate fast`
- **After setup:** NO_SHIP (exit 2, 82s, python from `.venv`). Steps: doctor ✅, ruff ✅, ruff_format ✅, pytest ❌.
  - First failure (test): `FAILED tests/test_requests.py::TestTimeout::test_connect_timeout[timeout0] - ...`
  - Next command: `PYTHONPATH=src python -m pytest -q tests/test_requests.py::TestTimeout::test_connect_timeout[timeout0] -o addopts=`

- Right: Fresh clone: NOT_RUN is right. The tests imported the requests 2.34.2 release installed next to SDETKit, not this checkout.
- Right: ruff and the format check get exactly the files of requests' pre-commit hooks, so `tests/test_lowlevel.py`, which its `ruff-format` hook excludes, is not format-checked. Setup installs `requirements-dev.txt`.
- Environment: After setup: NO_SHIP comes from four `TestTimeout` tests that expect a connection to the unroutable `10.255.255.1` to time out. This sandbox's network answers instead, so they fail here; the other 615 tests pass.

## Reproduce

```bash
python scripts/external_repo_proof.py run --workdir /tmp/external-repos
python scripts/external_repo_proof.py render
```

`run` needs network access to GitHub and the package indexes, plus `uv` and `poetry` on `PATH`, and rewrites `docs/artifacts/external-repo-proof/results.json`; `render` rebuilds this page from it. A test keeps the page and the results in step.
