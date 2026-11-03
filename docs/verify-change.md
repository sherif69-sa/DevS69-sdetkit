# Verify a change

`sdetkit verify change` checks a change from anyone, an AI coding agent included, by running it. It builds the change in a temporary clone, runs the tests on the base and on the change, and checks that the tests were not weakened to make them pass. Your working tree is never modified.

```bash
# A patch file (an agent's diff, a downloaded PR diff) on top of a base commit.
python -m sdetkit verify change --patch agent.diff --base origin/main

# The uncommitted work, untracked files included, against HEAD (the index is not touched).
python -m sdetkit verify change --working-tree

# A branch or commit that holds the change.
python -m sdetkit verify change --base origin/main --head feature/agent-fix

# Only some tests: everything after `--` goes to pytest.
python -m sdetkit verify change --base origin/main --head my-branch -- tests/test_api.py
```

## What it checks

| Check | Finding | Status |
| --- | --- | --- |
| The patch applies to the base | `verify change error: the patch does not apply` | exit 2 |
| A test that passed on the base fails on the change, or a new test fails | regressions, new failures | `FAILED` |
| A test that existed on the base is gone (by name, and by what pytest ran) | `tests_removed`, missing tests | `REVIEW` |
| A test was renamed or moved to another test file with its body, arguments and decorators unchanged | `tests_renamed` (not counted as removed or missing) | note only |
| A test that checked something now asserts nothing (asserting a constant such as `True` counts as nothing) | `assertions_removed` | `REVIEW` |
| A test makes fewer assertions (counting the assertions in helpers from the same file that it calls) | `assertions_reduced` | `REVIEW` |
| A test gained `skip`, `skipif` or `xfail` (decorator, `pytestmark` or a call), or passed before and is skipped now | `skip_added`, now skipped | `REVIEW` |
| The pytest configuration changed (`pytest.ini`, `tox.ini`, `setup.cfg`, `[tool.pytest]`) | `test_config_changed` | `REVIEW` |
| `fail_under` went down or was removed | `coverage_threshold_lowered` | `REVIEW` |
| A test that failed before still fails | still failing | `REVIEW` |
| A test in the changed test files fails on the code before the change and passes with it | proving test (the change does what its test checks) | shown as **Proof** |
| No test in the changed test files fails on the code before the change | `tests_do_not_prove_the_change` | note only (right for a refactor) |
| `conftest.py`, `noxfile.py` or a CI workflow changed | `test_harness_changed` | note only |
| pytest is missing, the run timed out, no test ran, or the tests would import the changed package from outside the clone (an editable install of another checkout) | | `NOT_RUN` |

When none of these apply and every test passed, the status is `VERIFIED`. That means the tests pass and were not weakened. It does not mean the change is correct, safe or what you asked for: read it.

The exit code is 0 for `VERIFIED`, 1 for `REVIEW`, and 2 for `FAILED`, `NOT_RUN` or a usage error.

## What you get

Everything is written to `build/sdetkit/change-verification/` unless you pass `--out-dir`:

| File | What it holds |
| --- | --- |
| `change-verification.md` | The status, the reasons and every finding, for a person |
| `change-verification.json` | The full report (`sdetkit.change_verification.v1`) with the shared `sdetkit.verdict.v1` |
| `change.patch` | The change as verified: `git diff --binary base head` |
| `tests-base.xml`, `tests-proof.xml`, `tests-head.xml` | The JUnit results: the base, the changed test files on the base code, the change |
| `change-verification.intoto.json` | An [in-toto Statement](https://github.com/in-toto/attestation) about the change |
| `change-verification.predicate.json` | The same predicate on its own, for tools that take one |

The Statement's subject is the SHA-256 of `change.patch` and, for `--head`, the head commit. Its predicate (`https://sherif69-sa.github.io/DevS69-sdetkit/attestations/change-verification/v1`) records the base and head commits, the status, the test counts, the finding codes, the SDETKit version and the SHA-256 of every evidence file.

SDETKit does not sign it itself. In GitHub Actions the action below can sign it with GitHub artifact attestations (`attest: "true"`); elsewhere use the tool you already have, for example `cosign attest-blob --predicate build/sdetkit/change-verification/change-verification.predicate.json --type <predicate type> build/sdetkit/change-verification/change.patch`.

## In GitHub Actions

The `verify-change` action runs `verify change` on every pull request, puts the status in the job summary, posts it as one comment on the pull request (updated on each push) and uploads the evidence as an artifact:

```yaml
name: Verify change

on: pull_request

permissions:
  contents: read
  pull-requests: write # for the pull request comment

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0 # the verifier needs the base and the head commit
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -e ".[test]" # however your project installs its tests' dependencies
      - uses: sherif69-sa/DevS69-sdetkit/verify-change@main
```

!!! note "Not in 2.0.0"
    The action is newer than the 2.0.0 release. Use `@main`, or pin a commit SHA from `main`, until the next release is tagged.

The change it verifies is the pull request's own: from the commit where the branch left its base (`git merge-base`) to the pull request's head commit, the same diff as the "Files changed" tab. Outside a pull request it verifies `HEAD~1` to `HEAD`; set `base` and `head` to choose, or `patch` to verify a diff file an earlier step produced.

The comment looks like this:

```markdown
### :warning: SDETKit verify change: REVIEW

`3f1c2a9b8d7e` → `9a8b7c6d5e4f`, 3 file(s) changed.

| Run | Tests |
| --- | --- |
| Base | 214 passed, 0 failed, 0 skipped |
| Change | 213 passed, 0 failed, 0 skipped |

- tests_removed: Tests that existed before the change are gone.
- 1 test(s) ran before and did not run now

- **tests_removed**: Tests that existed before the change are gone. `tests/test_api.py::test_rejects_expired_token`
```

### Inputs

| Input | Default | What it does |
| --- | --- | --- |
| `base`, `head` | the pull request's, else `HEAD~1` and `HEAD` | The commits to compare |
| `patch` | | Verify this diff file on top of `base` instead of a head commit |
| `pytest-args` | the whole suite | Arguments for the test runner, such as `tests/unit -x` |
| `runner` | `auto` | `pytest`, `vitest`, `jest` or `node`; see [JavaScript and TypeScript](#javascript-and-typescript) |
| `base-run` | `targeted` | What runs on the base: `targeted`, `full` or `none` (see [How it runs](#how-it-runs)) |
| `python` | the repository's environment, else the job's `python` | Interpreter that runs the tests |
| `fail-on` | `FAILED,NOT_RUN` | Statuses that fail the step, or `none`. Add `REVIEW` to block changes that weaken tests until a person approves them |
| `comment` | `true` | Post and update one pull request comment (needs `pull-requests: write`) |
| `upload-artifact`, `artifact-name` | `true`, `sdetkit-change-verification` | Upload the report, patch, JUnit files and attestation |
| `attest` | `false` | Sign the attestation with [GitHub artifact attestations](https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations); needs `id-token: write` and `attestations: write` |
| `working-directory` | `.` | Repository root, for a project in a subfolder |
| `sdetkit-version` | the action's own source | Install this sdetkit version from PyPI instead |

Outputs: `status` (`VERIFIED`, `REVIEW`, `FAILED`, `NOT_RUN`), `verdict` (the shared `SHIP`, `REVIEW`, `NO_SHIP`, `NOT_RUN`), and the paths of the `report`, `summary`, `attestation` and `patch`.

### For pull requests opened by AI agents

Gate agent pull requests on `REVIEW` as well, and sign what was verified:

```yaml
permissions:
  contents: read
  pull-requests: write
  id-token: write
  attestations: write

# ...
      - uses: sherif69-sa/DevS69-sdetkit/verify-change@main
        with:
          fail-on: FAILED,NOT_RUN,REVIEW
          attest: "true"
```

Run it on `pull_request`, not `pull_request_target`: the tests execute the pull request's code, and `pull_request` gives code from forks a read-only token. On a fork the comment cannot be posted; the step warns and the job summary still has the status.

## JavaScript and TypeScript

The same checks run on vitest, jest and `node --test` suites:

```bash
npm ci  # the clone uses the repository's installed packages
python -m sdetkit verify change --base origin/main --head my-branch
python -m sdetkit verify change --runner vitest --base origin/main --head my-branch -- src/cart
```

- `--runner auto` (the default) runs pytest in a Python project (one with `pyproject.toml`, `setup.py`, `setup.cfg`, `pytest.ini` or `tox.ini`) and otherwise the runner `package.json` names in its dependencies or its `test` script. Pass `--runner pytest|vitest|jest|node` to choose.
- vitest and jest come from the repository's `node_modules`: the clone gets links to the installed packages, and its own folder for their caches, so nothing is written in your checkout. Without them the status is `NOT_RUN`. `node --test` needs only `node`.
- Test files are the runners' defaults: `*.test.*` and `*.spec.*` (`.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`, `.mts`, `.cts`), files under `__tests__/` and `test/`, and `test-*` / `*-test` / `*_test` files. A test is named by its `describe` groups and its title, `__tests__/cart.test.ts::cart > adds an item`.
- What the test files say is read from the source: `expect(...)` and `assert...(...)` calls count as assertions (`expect(true)` does not), `.skip`, `xit`, `xdescribe`, `skipIf`, `{ skip: ... }`, `t.skip()` and pending (not yet written) tests count as skips, and `.only`, `fit` or `fdescribe` give `only_added`, since the other tests in the file stop running. A change to `vitest.config.*`, `jest.config.*`, or the `jest` section or `test` script of `package.json` gives `test_config_changed`.
- These runners have no collection step, so `--base-run targeted` runs the whole suite on the base for them.

## How it runs

- The repository is cloned into a temporary folder; `--patch` is applied there with `git apply --index` and committed, `--head` is checked out there. The canonical patch is the diff between the two commits, so what is attested is what ran.
- The tests run with the project's own interpreter (the same one `gate fast` finds; override with `--python`), with the clone's `src/` and root first on the import path, so the clone's code wins over an editable install of your checkout. Before the run, each changed package is located; if it would still come from outside the clone, the status is `NOT_RUN`.
- Commands get a reduced environment (`PATH`, `HOME`, temp folders, `VIRTUAL_ENV`, `CI`): no tokens or credentials are passed on.
- The change's tests run first, in full. What runs on the base is `--base-run`:
  - `targeted` (the default) collects the base's tests, so tests that no longer run are found, and re-runs on the base only the tests that failed or were skipped on the change, so a regression is told from a failure that was already there. The suite runs about once.
  - `full` runs the whole suite on the base too. It costs a second run and adds one list: tests that failed before and pass now.
  - `none` (also `--no-base-run`) skips the base. Every failing test then counts against the change, and missing tests are found by name only.
- The changed test files also run against the base code, whatever the mode, to find the tests that prove the change.

The tests execute the change's own code. Run `verify change` where you would run that code anyway: in CI or a sandbox, not on a machine with secrets in reach. Network isolation is not enforced (`network_isolated: false` in the report).
