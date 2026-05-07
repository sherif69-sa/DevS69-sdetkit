# SDETKit Quality Playbook

This repo uses a "quality gates" workflow:
- Tests: pytest
- Coverage: pytest-cov (branch coverage, fail-under)
- Lint/format: ruff
- Mutation testing: mutmut

The goal is not just "green tests", but tests that catch wrong implementations.

## Quick commands

### 1) Format + lint
ruff format .
ruff check .

### 2) Run unit tests
PYTHONPATH=src pytest -q

### 3) Coverage gate
bash quality.sh cov

### 4) Mutation testing (mutmut)
Recommended clean run:
rm -rf mutants .mutmut-cache .pytest_cache
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
mutmut run
mutmut results

## Coverage: how to read the report

Coverage output has:
- Stmts / Miss: lines executed or missed
- Branch / BrPart: branch coverage (if enabled)
- Missing: line numbers not executed

If total coverage fails:
1) Open the file and find the missing lines.
2) Add a test that reaches those branches.
3) Prefer behavior tests (inputs/outputs/errors) over internal implementation tests.

## Mutation testing: how to use it

Mutmut changes your code in small ways (mutations). If tests still pass, that mutant "survived".
Survivors mean: a behavior is not asserted strongly enough.

### Inspect a survivor
mutmut show <mutant_name>

Example:
mutmut show sdetkit.kvcli.x_main__mutmut_7

### Strategy to kill survivors
- Add assertions on:
  - return values / error codes
  - raised exception types
  - stdout/stderr content (only what matters, avoid brittle exact messages)
  - number of retries / attempts
  - edge cases: empty input, invalid input, non-2xx, timeout, IO failures

## Repo hygiene

Keep generated folders out of git:
- mutants/
- .mutmut-cache/
- .pytest_cache/
- __pycache__/
- .hypothesis/
- htmlcov/

## Platform work vs this repo

This bootcamp repo can keep tooling configs committed (ruff, coverage, mutmut).
For platform-style repos, avoid changing repo configs unless explicitly allowed.
Use CLI flags locally instead of committing config changes.

## Release

- Releases are triggered by pushing an annotated tag like vX.Y.Z.
- The tag version must exactly match pyproject.toml [project].version (enforced in CI).
- After releasing X.Y.Z, bump main to the next version before creating the next tag.

Example:
- update pyproject.toml version
- git tag -a vX.Y.Z -m "vX.Y.Z"
- git push origin vX.Y.Z
