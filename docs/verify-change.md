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
| Changed lines of code that no test runs (pytest, go test; see [Changed lines no test runs](#changed-lines-no-test-runs)) | `changed_lines_not_run` | note only; `REVIEW` below `--min-changed-coverage` |
| pytest is missing, the run timed out, no test ran, or the tests would import the changed package from outside the clone (an editable install of another checkout) | | `NOT_RUN` |

When none of these apply and every test passed, the status is `VERIFIED`. That means the tests pass and were not weakened. It does not mean the change is correct, safe or what you asked for: read it.

The exit code is 0 for `VERIFIED`, 1 for `REVIEW`, and 2 for `FAILED`, `NOT_RUN` or a usage error.

## What you get

Everything is written to `build/sdetkit/change-verification/` unless you pass `--out-dir`:

| File | What it holds |
| --- | --- |
| `change-verification.md` | The status, the reasons and every finding, for a person; for `FAILED`, why each broken test fails |
| `change-verification.json` | The full report (`sdetkit.change_verification.v1`) with the shared `sdetkit.verdict.v1` |
| `change.patch` | The change as verified: `git diff --binary base head` |
| `tests-base.xml`, `tests-proof.xml`, `tests-head.xml` | The JUnit results: the base, the changed test files on the base code, the change |
| `change-verification.intoto.json` | An [in-toto Statement](https://github.com/in-toto/attestation) about the change |
| `change-verification.predicate.json` | The same predicate on its own, for tools that take one |

When the status is `FAILED`, the report's `tests.failures` (and a **Why they fail** section in the Markdown, the job summary and the MCP result) holds each broken test's failure as its runner reported it: pytest's assertion and traceback, the vitest, jest or `node --test` error and stack, what a Go test printed and the compiler errors of a package that did not build, or a JUnit failure's message and stack from the Maven or Gradle reports. The runners' own stack frames are dropped, paths are relative to the repository, and each message keeps its last 1,500 characters, for the first 20 broken tests. Whoever made the change, an agent included, can fix it without running the suite again.

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
| `runner` | `auto` | `pytest`, `vitest`, `jest`, `node`, `go`, `maven` or `gradle`; see [JavaScript and TypeScript](#javascript-and-typescript), [Go](#go) and [Java](#java) |
| `network` | `allow` | `deny` runs the tests without the network; see [Without the network](#without-the-network) |
| `min-changed-coverage` | `0` | Percentage of the change's lines of code the tests must run; below it the status is `REVIEW` (see [Changed lines no test runs](#changed-lines-no-test-runs)) |
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
- These runners (and `go test`) have no collection step, so `--base-run targeted` runs the whole suite on the base for them.

## Go

`go test` suites run the same way, with `--runner go` or, in a repository with a `go.mod` and no Python or JavaScript test setup, on their own:

```bash
python -m sdetkit verify change --base origin/main --head my-branch
python -m sdetkit verify change --runner go --base origin/main --head my-branch -- ./internal/...
```

- Everything after `--` goes to `go test` as packages (the default is `./...`). Results come from `go test -json`; a test is named by its package directory and name, `internal/cart::TestAdd`, subtests `internal/cart::TestTable/empty`, and a package whose tests do not build is `::internal/cart`.
- In `*_test.go` files, `t.Error`, `t.Errorf`, `t.Fatal`, `t.Fatalf`, `t.Fail` and testify's `assert.*` / `require.*` count as assertions, including in same-file helpers a test calls (`require.True(t, true)` and `fmt.Errorf` do not). `t.Skip`, `t.Skipf` and `t.SkipNow` count as skips. Removed, emptied, skipped and renamed tests are caught as for pytest.
- `go test` takes packages, not files, so the proof run (the change's tests against the code before it) runs the packages of the changed test files.
- On google/uuid (212 tests), deleting `TestNew` reads `REVIEW` with `tests_removed`, in about 20 seconds.

## Java

Maven and Gradle builds run the same way, with `--runner maven` or `--runner gradle` or, in a repository with a `pom.xml` (Maven) or a `build.gradle`, `build.gradle.kts` or `settings.gradle(.kts)` (Gradle) and no Python, JavaScript or Go test setup, on their own:

```bash
python -m sdetkit verify change --base origin/main --head my-branch
python -m sdetkit verify change --runner maven --base origin/main --head my-branch -- -pl core
```

- The build runs `mvn test` or `gradle test`, with the project's `mvnw` or `gradlew` when it has one. Everything after `--` goes to the build tool. Maven runs with `-fae -Dmaven.test.failure.ignore=true` and Gradle with `--continue --no-build-cache`, so every module's tests run and none come from a cache.
- Results come from the JUnit XML reports (`target/surefire-reports`, `build/test-results`). A test is named by its class and method, `com.example.CartTest::adds`; a nested class is `com.example.CartTest$Empty::isEmpty`, and a run of a parameterized test `com.example.CartTest::positive(int)[1]`. Gradle's reports name such runs by their display name alone (`[1] 2`), so Gradle runs with a small init script that prints each test's own name, and the ids are the same as with Maven. A project whose code does not compile is `::<artifactId>` (Maven) or `::<project path>` (Gradle, `::.` for the root), with the compiler's errors as the reason.
- Test files are Surefire's default names (`Test*.java`, `*Test.java`, `*Tests.java`, `*TestCase.java`) and `*IT.java`. In a test method (`@Test`, `@ParameterizedTest`, `@RepeatedTest`, `@TestFactory`, `@TestTemplate`), JUnit's `assert*` and `fail`, AssertJ's and Hamcrest's `assertThat`, Mockito's `verify` and Java's `assert` count as assertions, including in methods of the same file the test calls, and so does JUnit 4's `@Test(expected = ...)`; `assertTrue(true)` does not. `@Disabled`, `@Ignore`, the `@EnabledIf...`/`@DisabledIf...` family (on the method or its class) and `assume*(...)` calls count as skips.
- A change to the Surefire, Failsafe or JaCoCo plugin settings or the test properties (`skipTests`, `maven.test.skip`, ...) of a `pom.xml`, or to the `test`, `tasks.withType<Test>` or `jacoco*` blocks of a Gradle build, gives `test_config_changed`. Dependency and version changes do not.
- The proof run selects the changed test classes (`-Dtest=` / `--tests`). A changed test class that does not compile against the code before the change (it uses something the change adds) fails there as a whole, so its tests prove the change.
- Install the JDK the project needs (`actions/setup-java` in a workflow). With `--network deny` the build runs offline (`-o` / `--offline`): run the tests once beforehand so the local Maven repository or Gradle cache has every dependency and plugin.

## Changed lines no test runs

Passing tests say nothing about code they never reach: a new branch, a function the tests do not call, a module nothing imports. While the tests run on the change, `verify change` records which lines run and reads the lines the change adds or modifies in source files against it:

```text
**Changed lines:** the tests run 2 of the 6 changed line(s) of code (33.3%).

- changed_lines_not_run (note): Changed lines of code that no test runs. `src/calc/__init__.py:8-9`, `src/calc/extra.py:1-2`
```

- Only lines of code count: comments, blank lines and the like are not code, and test files, `conftest.py`, `testdata/` and `vendor/` are not the code under test.
- pytest runs under coverage.py, with a configuration of its own (only the changed files' directories are measured, and the project's coverage thresholds and plugins do not apply), including pytest-xdist workers and other Python subprocesses with coverage.py 7.10 or later. coverage.py must be installed in the interpreter that runs the tests (`pip install coverage`; pytest-cov brings it); pytest-cov's own measurement is turned off for that run (`--no-cov`) so it does not take over. Without coverage.py the report says the coverage was not measured.
- `go test` runs with `-coverprofile` and `-coverpkg=./...`, so code that a test in another package runs counts, and a changed package with no tests reads as not run.
- The JavaScript and Java runners do not measure it yet.
- By default it is reported only. `--min-changed-coverage 80` (action input `min-changed-coverage`, MCP argument `min_changed_coverage`) makes a change whose tests run less than 80% of its changed lines of code `REVIEW`, and a change where it could not be measured `REVIEW` too. `--no-coverage` skips the measurement.
- The report holds it under `changed_coverage` (per file, the changed and run counts and the lines not run), and the attestation under `changed_lines`.

## Without the network

For a change you do not trust yet, a coding agent's or a fork's, run its tests without the network:

```bash
python -m sdetkit verify change --network deny --base origin/main --head agent-branch
```

- Every command that runs the repository's code (the test runs on the change and the base, the proof run, pytest's collection) runs in a Linux network namespace of its own, through `unshare --user --map-root-user --net`. Inside, the loopback interface is brought up, so tests can still start and reach servers on `127.0.0.1`; nothing outside the namespace, the host's own loopback included, is reachable.
- Before anything runs, the namespace is checked: a child process must get a different network namespace and fail to reach a server the parent opened. Where that check fails (macOS, Windows, or Linux with unprivileged user namespaces turned off), `--network deny` stops with an error instead of running with the network.
- GitHub's Ubuntu 24.04 runners restrict unprivileged user namespaces (`kernel.apparmor_restrict_unprivileged_userns=1`). With `network: deny`, the action lifts that restriction on a GitHub-hosted runner, a machine that exists only for the job, and says so in a notice. It never changes a self-hosted runner: there, allow unprivileged user namespaces yourself or the run stops with the reason.
- The report and the attestation say so: `network_isolated: true`, and `network` gives the mode and the backend.
- Install dependencies before the run (`pip install`, `npm ci`, `go mod download`, one `mvn test` or `gradle test`): nothing can be downloaded during it. Inside the namespace the tests run as its root user, which maps to your own user outside; a test that expects a permission error on its own files can fail there, on the base and the change alike.
- On google/uuid, deleting `TestJSON` reads `REVIEW` with `tests_removed` and `network_isolated: true`, in about 5 seconds.

## How it runs

- The repository is cloned into a temporary folder; `--patch` is applied there with `git apply --index` and committed, `--head` is checked out there. The canonical patch is the diff between the two commits, so what is attested is what ran.
- The tests run with the project's own interpreter (the same one `gate fast` finds; override with `--python`), with the clone's `src/` and root first on the import path, so the clone's code wins over an editable install of your checkout. Before the run, each changed package is located; if it would still come from outside the clone, the status is `NOT_RUN`.
- Commands get a reduced environment (`PATH`, `HOME`, temp folders, `VIRTUAL_ENV`, `CI`): no tokens or credentials are passed on.
- The change's tests run first, in full. What runs on the base is `--base-run`:
  - `targeted` (the default) collects the base's tests, so tests that no longer run are found, and re-runs on the base only the tests that failed or were skipped on the change, so a regression is told from a failure that was already there. The suite runs about once.
  - `full` runs the whole suite on the base too. It costs a second run and adds one list: tests that failed before and pass now.
  - `none` (also `--no-base-run`) skips the base. Every failing test then counts against the change, and missing tests are found by name only.
- The changed test files also run against the base code, whatever the mode, to find the tests that prove the change.

The tests execute the change's own code. Run `verify change` where you would run that code anyway: in CI or a sandbox, not on a machine with secrets in reach. By default the tests can use the network (`network_isolated: false` in the report); `--network deny` [takes it away](#without-the-network). Only the network is isolated: the files the tests can reach are your user's.
