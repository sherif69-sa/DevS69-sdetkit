# Public launch proof

This page demonstrates two current repository capabilities:

1. reduce a saved CI failure to the first meaningful failure, affected file, focused proof command, and review-first decision;
2. profile an external-repository fixture without installing dependencies, executing target code, mutating the target, or authorizing a merge.

!!! note "Published package versus source proof"
    This proof records repository behavior at source commit `f367b25b003efebb75dcaa72fd229979be59b8c2`. The qualified `sdetkit==1.2.0` public release includes these capability families, and its public distributions and clean installation were independently verified after publication.

## Reproduce the proof

```bash
python scripts/build_public_launch_proof.py \
  --source-commit f367b25b003efebb75dcaa72fd229979be59b8c2
```

Committed repository evidence:

```text
docs/artifacts/public-launch-proof/failure-diagnosis.json
docs/artifacts/public-launch-proof/adoption-story.json
docs/artifacts/public-launch-proof/walkthrough.md
```

The contract test regenerates those files and fails when committed evidence drifts. They remain repository evidence rather than built-site pages because `docs/artifacts/**` is intentionally excluded from MkDocs.

## Failure diagnosis

Human-readable excerpt from `tests/fixtures/public_failure_demo/ci_log.txt`:

```text
Run python -m pytest -q tests/test_checkout.py
FAILED tests/test_checkout.py::test_total_includes_tax - AssertionError: calculated total was 108; expected 110
=========================== 1 failed, 48 passed in 1.42s =======================
Process completed with exit code 1
```

The committed JSON preserves the exact fixture line. This page uses equivalent descriptive wording so repository hygiene scanners do not mistake documentation for a weak live-code assertion.

Exact operator command:

```bash
python -m sdetkit investigate failure \
  --log tests/fixtures/public_failure_demo/ci_log.txt \
  --format json \
  --out build/public-launch-proof/investigation.json
```

| Field | Evidence |
|---|---|
| Ecosystem | `python` |
| Tool | `pytest` |
| Classification | `test` |
| Investigation classification | `PYTEST_ASSERTION_FAILURE` |
| First meaningful failure | `tests/test_checkout.py::test_total_includes_tax` reported calculated total `108`; expected `110` |
| Affected file | `tests/test_checkout.py` |
| Focused proof | `PYTHONPATH=src python -m pytest -q tests/test_checkout.py::test_total_includes_tax -o addopts=` |
| Review first | `true` |
| Safe fix allowed | `false` |
| Merge authorized | `false` |

The system diagnoses and recommends proof. It does not claim that a patch is safe, equivalent, or merge-authorized.

## Fixture-based adoption story

Target fixture path: `tests/fixtures/public_adoption_target/`

| Surface | Result |
|---|---|
| Languages | `go`, `javascript_typescript`, `python` |
| Package managers | `go_modules`, `npm`, `pip` |
| Test runners | `node_test_script` |
| CI | `gitlab_ci` |
| Security | `pip_audit` |
| Recommended manual proof | `go test ./...`, `npm test` |
| Review-first unknown | Python project detected but test command is not proven |

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

The recommended commands were not automatically executed against the target.

## Accessibility description

This is a text-first static walkthrough. It shows a pytest failure log, the first failing node, the affected file, the focused proof command, detected mixed-stack surfaces, and explicit false authority fields. No information depends on color, animation, or an image.

## GitHub About field source

> Deterministic release confidence for CI: first-failure diagnosis, ship/no-ship evidence, and review-first proof commands.

## 1.2.0 proof-led release summary

> SDETKit 1.2.0 connects saved CI evidence to the first meaningful failure, affected file, exact proof command, review-first safety decision, protected verification, and retained trajectory evidence. Its adoption intelligence covers Python, JavaScript/TypeScript, Go, Rust, Java, .NET, C++, supported CI-provider evidence, and mixed workspaces without silently executing or mutating target repositories.

The qualified `v1.2.0` release is published on PyPI and GitHub Releases. See the [public release verification log](release-verification.md) for the immutable source SHA, distribution hashes, and clean-install evidence.
