# Public launch proof

This page is the concise, accessible proof behind SDETKit's public product claim.

It demonstrates two current `main` capabilities:

1. reduce a realistic saved CI failure to the first meaningful failure, affected file, focused proof command, and review-first decision;
2. profile an external-repository fixture without installing dependencies, executing target code, mutating the target, or authorizing a merge.

!!! note "Published package versus main"
    These artifacts prove repository `main` behavior at source commit `f367b25b003efebb75dcaa72fd229979be59b8c2`. They are **main-only until the qualified 1.1.0 release**. The currently published `1.0.3` wheel must not be treated as proof of these surfaces.

## Reproduce the committed proof

```bash
python scripts/build_public_launch_proof.py \
  --source-commit f367b25b003efebb75dcaa72fd229979be59b8c2
```

Committed outputs:

- [Failure-diagnosis JSON](artifacts/public-launch-proof/failure-diagnosis.json)
- [Fixture-based adoption JSON](artifacts/public-launch-proof/adoption-story.json)
- [Accessible static walkthrough](artifacts/public-launch-proof/walkthrough.md)

The contract test regenerates these files and fails when committed evidence drifts from current behavior.

## Failure diagnosis demonstration

### Visible input

```text
Run python -m pytest -q tests/test_checkout.py
...
FAILED tests/test_checkout.py::test_total_includes_tax - AssertionError: assert 108 == 110
=========================== 1 failed, 48 passed in 1.42s =======================
Process completed with exit code 1
```

Full fixture: [`tests/fixtures/public_failure_demo/ci_log.txt`](../tests/fixtures/public_failure_demo/ci_log.txt)

### Exact operator command

```bash
python -m sdetkit investigate failure \
  --log tests/fixtures/public_failure_demo/ci_log.txt \
  --format json \
  --out build/public-launch-proof/investigation.json
```

### Deterministic result

| Field | Evidence |
|---|---|
| Ecosystem | `python` |
| Tool | `pytest` |
| Classification | `test` |
| Investigation classification | `PYTEST_ASSERTION_FAILURE` |
| First meaningful failure | `FAILED tests/test_checkout.py::test_total_includes_tax - AssertionError: assert 108 == 110` |
| Affected file | `tests/test_checkout.py` |
| Focused proof | `PYTHONPATH=src python -m pytest -q tests/test_checkout.py::test_total_includes_tax -o addopts=` |
| Review first | `true` |
| Safe fix allowed | `false` |
| Merge authorized | `false` |

The system diagnoses and recommends proof. It does not claim that a patch is safe, equivalent, or merge-authorized.

## Fixture-based external adoption story

Target fixture: [`tests/fixtures/public_adoption_target/`](../tests/fixtures/public_adoption_target/)

The fixture intentionally represents a mixed repository with Python, JavaScript/TypeScript, Go, GitLab CI, and `pip-audit` evidence.

Detected surfaces:

| Surface | Result |
|---|---|
| Languages | `go`, `javascript_typescript`, `python` |
| Package managers | `go_modules`, `npm`, `pip` |
| Test runners | `node_test_script` |
| CI | `gitlab_ci` |
| Security | `pip_audit` |
| Recommended manual proof | `go test ./...`, `npm test` |
| Review-first unknown | Python project detected but test command is not proven |

Safety evidence:

```text
read_only=true
dependencies_installed=false
target_code_executed=false
target_repository_mutated=false
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

The recommended commands are evidence for a human operator. They were not automatically executed against the target.

## Accessibility description

This is a text-first static walkthrough. The first panel is a pytest failure log. The second panel highlights the first failing node, affected test file, and focused pytest command. The final panel lists detected mixed-stack repository surfaces and shows every authority or mutation field as false. No information depends on color, animation, or an image.

## GitHub About field source

> Deterministic release confidence for CI: first-failure diagnosis, ship/no-ship evidence, and review-first proof commands.

## 1.1.0 proof-led announcement draft

> SDETKit 1.1.0 turns saved CI evidence into a first meaningful failure, affected file, focused proof command, and explicit review-first decision. Its adoption profiler can identify Python, JavaScript/TypeScript, Go, CI, and security surfaces without installing target dependencies, executing target code, changing the target repository, or authorizing a merge. The release is published only after exact-wheel qualification, trusted publishing, and public-install verification complete.

This announcement remains a draft until the qualified `1.1.0` release workflow succeeds and the public package is verified.
