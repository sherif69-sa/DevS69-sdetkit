# Frequently asked questions

## What do the four verdicts mean?

Every run ends in one decision in `verdict.decision`:

- **`SHIP`**: every check ran against this repository and passed.
- **`REVIEW`**: nothing blocks, but a person should look first (findings that do not block, or a proven fix waiting for approval).
- **`NOT_RUN`**: the checks could not run against this repository, so nothing was proven either way.
- **`NO_SHIP`**: a check failed.

The [home page](index.md#one-verdict-per-run) has a table of what to do for each.

## Why did I get `NOT_RUN`?

Because nothing was proven about your code: either the checks could not run in this environment, or there was nothing to check. `gate fast` reports `NOT_RUN` when:

- pytest could not import your own package (the project is not installed where the tests ran);
- the tests ran in SDETKit's own interpreter, with no project environment, and a dependency was missing;
- the tests imported another installed release of your project instead of the checkout;
- mypy failed only inside installed packages, or the project and its dependencies are not installed at all;
- the project environment has no pytest;
- a non-Python suite's tool (for example `go` or `npm`) is not installed;
- there was nothing to check: the repository has no tests and no ruff or mypy configuration, as in a brand-new repository. `verdict.next_action` then says what to add.

Otherwise `next_action.next_command` gives the setup command for your repository, such as `uv sync && python -m sdetkit gate fast`. The [external repository proof](external-repo-proof.md) shows this on fresh clones of seven open-source projects.

## Does SDETKit change my repository?

No, unless you ask it to. The gate, doctor and diagnosis commands read your repository and write their results under `build/` and `.sdetkit/` (or the paths you pass with `--out`). `diagnose run --prove` tests a candidate fix in a throwaway copy, never in your working tree, and every authority flag in SDETKit's output (`patch_application_allowed`, `merge_authorized` and the others) is `false`. The only options that edit files are `gate fast --fix` and `--fix-only`, which apply `ruff check --fix` and `ruff format`.

## Does it run my code?

Yes: `gate fast` runs your repository's own tests and tools, exactly as you would. Run it on code you would run `pytest` on, and use an isolated environment for code you do not trust. The [security policy](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/SECURITY.md) describes the security model.

## Does it need network access?

`gate fast`, `gate release`, `doctor` and `diagnose run` make no network requests of their own, and the security scan reads your lockfiles locally. Your own tests may still use the network.

## Which Python runs my checks?

The project's own environment: `--python`, then `.venv` or `venv` in the repository, then Poetry's or Pipenv's environment, then an activated virtualenv (in the pre-commit hook, the `python` on `PATH`), then SDETKit's interpreter. See [configuration](configuration.md#which-python-runs-the-checks).

## Why did the gate check these files and not others?

It follows your repository's own settings: `files` in your mypy configuration, then your pre-commit hooks, then `tox.ini`, then a default. [Configuration](configuration.md#how-gate-fast-chooses-what-to-check) lists the order, and each step's `targets_from` says which source it used.

## How do I run or skip one step?

```bash
python -m sdetkit gate fast --list-steps
python -m sdetkit gate fast --only pytest
python -m sdetkit gate fast --skip mypy
```

To change a step permanently, set `pytest_args`, `mypy_args` or `ruff_paths` under `[tool.sdetkit.gate]` in `pyproject.toml` ([configuration](configuration.md)).

## What exit codes does the gate use?

`gate fast` exits `0` when every step passed and `2` when any step failed, including steps that could not run against the repository (`NOT_RUN` from the environment), so a broken CI setup never turns green. A non-Python suite whose tool is not installed is skipped: the run exits `0` but the verdict is `NOT_RUN`, so read `verdict.decision`, not only the exit code.

## A gate failed. How do I fix it?

Start from `next_action`: it names the first failure, the file and the command that reproduces it. Then:

```bash
python -m sdetkit diagnose run --prove
```

diagnoses the latest failing gate, proves the narrowest mechanical fix in a throwaway copy and writes a decision card for a person to approve. See the [remediation loop](remediation-loop.md) and [first-failure triage](first-failure-triage.md).

## Does it work outside Python?

Yes. The repository model recognises Python, JavaScript/TypeScript, Go, Java, Rust, .NET and C++ test suites and runs each workspace's own test command (for example `go test ./...`, `npm test` or `cargo test`). ruff, mypy and pytest run only where the repository has Python.

## Which version should I install?

The latest published package is `sdetkit==1.2.0`. These docs follow `main`, the 2.0.0 release candidate; [what's new in 2.0](current-product-delta.md) lists what is on `main` only until 2.0.0 is released.

## How do I use it in CI?

Run the same commands as locally and keep the JSON artifacts. The [recommended CI flow](recommended-ci-flow.md) and the GitHub Actions, GitLab and Jenkins reference packs have ready-made pipelines.

## Where do I report a bug or a vulnerability?

Bugs: [open an issue](https://github.com/sherif69-sa/DevS69-sdetkit/issues/new/choose) with `build/gate-fast.json` and the output of `python -m sdetkit doctor`. Vulnerabilities: report them privately as described in the [security policy](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/SECURITY.md).
