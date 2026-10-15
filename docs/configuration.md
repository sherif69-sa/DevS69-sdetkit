# Configuration

SDETKit works without configuration: `gate fast` reads the policy your repository already declares (its ruff, mypy and pytest settings, its pre-commit hooks, its `tox.ini`) and runs it in the project's own environment. Configuration is for the cases where you want something different. Everything lives in `pyproject.toml` under `[tool.sdetkit.*]`, and command-line flags override it.

## `[tool.sdetkit.gate]`: what `gate fast` runs

```toml
[tool.sdetkit.gate]
pytest_args = ["-q", "tests/unit"]
mypy_args = ["src"]
ruff_paths = ["src", "tests"]
doctor_args = ["--dev", "--deps", "--clean-tree"]
ci_templates = false
```

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `pytest_args` | list of strings | `["-q"]` when tests are detected | Arguments for the `pytest` step. |
| `mypy_args` | list of strings | see [how mypy targets are chosen](#how-gate-fast-chooses-what-to-check) | Arguments for the `mypy` step. |
| `ruff_paths` | list of strings | `src` and `tests` (whichever exist), else `.` | Paths for `ruff check` and `ruff format --check`. |
| `doctor_args` | list of strings | `["--dev", "--deps", "--clean-tree"]` | Arguments for the `doctor` step. |
| `ci_templates` | boolean | `false` | Run SDETKit's CI template validation (`ci_templates` step). |

An invalid value (for example a string where a list is expected) stops the gate with an error that names the key.

### How `gate fast` chooses what to check

For each tool, the first source that applies wins:

**mypy**

1. `--mypy-args` on the command line
2. `mypy_args` in `[tool.sdetkit.gate]`
3. `files` in your mypy configuration (`[tool.mypy]`, `mypy.ini`, `.mypy.ini` or `setup.cfg`): the gate runs plain `mypy`
4. your pre-commit mypy hook: its arguments as they are with `pass_filenames: false`, otherwise its arguments plus the files it selects
5. each `mypy ...` command in `tox.ini`, run in order
6. `mypy src` (or `mypy .` without a `src` directory)

The step is skipped when mypy is not configured at all.

**ruff**

1. `ruff_paths` in `[tool.sdetkit.gate]`
2. the files your pre-commit `ruff`/`ruff-check` and `ruff-format` hooks would check, when the hook or the config's top level sets `files` or `exclude`
3. `src` and `tests`, or `.`

The step is skipped when ruff is not configured (`[tool.ruff]`, `ruff.toml`, `.ruff.toml` or a pre-commit ruff hook).

**pytest**

1. `--pytest-args` on the command line, or `--full-pytest` for plain `pytest -q`
2. `pytest_args` in `[tool.sdetkit.gate]`
3. `pytest -q` when the repository has tests (`tests/`, `test/`, a `conftest.py`, or pytest configuration)

Each step records where its targets came from in `targets_from` when the repository's pre-commit or tox configuration supplied them.

### Which Python runs the checks

ruff, mypy and pytest run in the project's own environment, the first of:

1. `--python <interpreter>`
2. `.venv` or `venv` in the repository
3. Poetry's or Pipenv's environment, when the repository has `poetry.lock` or `Pipfile.lock`
4. an activated virtualenv (`VIRTUAL_ENV`)
5. the interpreter SDETKit itself runs in

The `environment` field of the gate's JSON names the interpreter and where it came from. See [which Python runs your checks](cli.md#which-python-runs-your-checks) for how failures that come from the environment are reported.

## `[tool.sdetkit.doctor]`

```toml
[tool.sdetkit.doctor]
release_tag_check_script = "scripts/check_release_tag_version.py"
```

| Key | Type | Effect |
| --- | --- | --- |
| `release_tag_check_script` | string | `doctor --release` requires `.github/workflows/release.yml` to run this script, which checks that the release tag matches the package version. Without it, the release workflow check is not required. |

## Other sections

| Section | Used by | Reference |
| --- | --- | --- |
| `[tool.sdetkit.repo_audit]` | `repo audit` | `profile`, `fail_on`, `baseline_path`, `exclude_paths`, `disable_rules`, `severity_overrides`, `org_packs`, `lint_expiry_max_days`: see [policy and baselines](policy-and-baselines.md) |
| `[tool.sdetkit.projects]` | monorepo commands | project roots and `autodiscover`: see [monorepo projects](monorepo-projects.md) |

## Command-line flags for `gate fast`

| Flag | Effect |
| --- | --- |
| `--only ruff,pytest` / `--skip mypy` | Run only, or skip, the listed steps. `python -m sdetkit gate fast --list-steps` lists them. |
| `--no-doctor`, `--no-ruff`, `--no-mypy`, `--no-pytest`, `--no-tests` | Leave out one step. |
| `--python <interpreter>` | Run the repository's checks with this interpreter. |
| `--profile adoption` | Run only `doctor`: prove SDETKit installs and emits evidence before enforcing the repository's policy. |
| `--strict` | Run `doctor` with `--fail-on medium` instead of `high`. |
| `--fix` / `--fix-only` | Apply `ruff check --fix` and `ruff format` first (`--fix-only` stops there). These are the only options that change your files. |
| `--format json --stable-json --out build/gate-fast.json` | Write the machine-readable result; `--stable-json` leaves out timings and machine-specific paths. |

The [CLI reference](cli.md) covers every command.
