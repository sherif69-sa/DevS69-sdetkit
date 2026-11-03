# Verify a change

`sdetkit verify change` checks a change from anyone, an AI coding agent included, by running it. It builds the change in a temporary clone, runs the tests on the base and on the change, and checks that the tests were not weakened to make them pass. Your working tree is never modified.

```bash
# A patch file (an agent's diff, a downloaded PR diff) on top of a base commit.
python -m sdetkit verify change --patch agent.diff --base origin/main

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
| A test that checked something now asserts nothing (asserting a constant such as `True` counts as nothing) | `assertions_removed` | `REVIEW` |
| A test makes fewer assertions | `assertions_reduced` | `REVIEW` |
| A test gained `skip`, `skipif` or `xfail` (decorator, `pytestmark` or a call), or passed before and is skipped now | `skip_added`, now skipped | `REVIEW` |
| The pytest configuration changed (`pytest.ini`, `tox.ini`, `setup.cfg`, `[tool.pytest]`) | `test_config_changed` | `REVIEW` |
| `fail_under` went down or was removed | `coverage_threshold_lowered` | `REVIEW` |
| A test that failed before still fails | still failing | `REVIEW` |
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
| `tests-base.xml`, `tests-head.xml` | The JUnit results of both runs |
| `change-verification.intoto.json` | An [in-toto Statement](https://github.com/in-toto/attestation) about the change |
| `change-verification.predicate.json` | The same predicate on its own, for tools that take one |

The Statement's subject is the SHA-256 of `change.patch` and, for `--head`, the head commit. Its predicate (`https://sherif69-sa.github.io/DevS69-sdetkit/attestations/change-verification/v1`) records the base and head commits, the status, the test counts, the finding codes, the SDETKit version and the SHA-256 of every evidence file.

SDETKit does not sign it. Sign it with the tool you already use, for example in GitHub Actions:

```yaml
- run: python -m sdetkit verify change --base origin/main --head "$GITHUB_SHA"
- uses: actions/attest@v2
  with:
    subject-path: build/sdetkit/change-verification/change.patch
    predicate-type: https://sherif69-sa.github.io/DevS69-sdetkit/attestations/change-verification/v1
    predicate-path: build/sdetkit/change-verification/change-verification.predicate.json
```

or locally with `cosign attest-blob --predicate build/sdetkit/change-verification/change-verification.predicate.json --type <predicate type> build/sdetkit/change-verification/change.patch`.

## How it runs

- The repository is cloned into a temporary folder; `--patch` is applied there with `git apply --index` and committed, `--head` is checked out there. The canonical patch is the diff between the two commits, so what is attested is what ran.
- The tests run with the project's own interpreter (the same one `gate fast` finds; override with `--python`), with the clone's `src/` and root first on the import path, so the clone's code wins over an editable install of your checkout. Before the run, each changed package is located; if it would still come from outside the clone, the status is `NOT_RUN`.
- Commands get a reduced environment (`PATH`, `HOME`, temp folders, `VIRTUAL_ENV`, `CI`): no tokens or credentials are passed on.
- `--no-base-run` skips the base run. It is faster, but every failing test then counts against the change, and missing tests are found by name only.

The tests execute the change's own code. Run `verify change` where you would run that code anyway: in CI or a sandbox, not on a machine with secrets in reach. Network isolation is not enforced (`network_isolated: false` in the report).
