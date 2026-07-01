# Public launch proof walkthrough

Accessible static walkthrough: a saved pytest CI log is reduced to the first failing node, its owning file, a focused proof command, and an explicit review-first decision. A separate fixture repository is then profiled without installing dependencies, executing target code, or modifying the target.

## Failure diagnosis

- source commit: `f367b25b003efebb75dcaa72fd229979be59b8c2`
- input log: `tests/fixtures/public_failure_demo/ci_log.txt`
- classification: `test`
- first failure: `FAILED tests/test_checkout.py::test_total_includes_tax - AssertionError: assert 108 == 110`
- affected file: `tests/test_checkout.py`
- proof command: `PYTHONPATH=src python -m pytest -q tests/test_checkout.py::test_total_includes_tax -o addopts=`
- review first: `true`
- merge authorized: `false`

## Fixture-based adoption story

- target: `tests/fixtures/public_adoption_target`
- languages: `go, javascript_typescript, python`
- package managers: `go_modules, npm, pip`
- CI systems: `gitlab_ci`
- security tools: `pip_audit`

### Review-first unknowns

- Python project detected but test command is not proven

### Safety proof

- dependencies installed: `false`
- target code executed: `false`
- target repository mutated: `false`
- automation allowed: `false`
- merge authorized: `false`
