# Quality truth baseline

SDETKit uses staged quality gates. This page records what is enforced today, what is only measured, and what remains incomplete so a green check cannot be interpreted more broadly than the evidence supports.

Contract: [`docs/contracts/quality-truth-baseline.v1.json`](contracts/quality-truth-baseline.v1.json)

Validator:

```bash
python scripts/check_quality_truth_baseline.py \
  --out build/quality/quality-truth-check.json
```

## Coverage truth

- The critical reliability spine is currently enforced at 95% in canonical CI.
- `quality.sh` supports whole-package coverage through `COV_SCOPE=full`.
- A reviewed whole-package blocking threshold has not yet been established.
- Until a full-package artifact and baseline are produced, the repository must not describe the whole package as 95% covered.

The planned full-package artifact path is:

```text
build/quality/coverage-full.json
```

## Typing truth

The repository still has a broad `sdetkit.*` mypy suppression. A reviewed group of diagnostic, safety, trajectory, and adoption modules explicitly opts back into error checking.

The contract lists those modules exactly. The validator fails when the configured list and recorded list drift apart.

This is a visible migration state, not a completion claim:

```text
blanket_package_suppression_present=true
migration_complete=false
new_unrecorded_suppression_allowed=false
```

## Runtime truth

The package metadata declares Python 3.10, 3.11, and 3.12. Canonical fast and smoke CI currently cover Python 3.11 and 3.12. Python 3.10 appears in the first-proof route, but full CI and exact-wheel qualification across all three versions remain release work.

## Required next steps

1. Produce a deterministic whole-package coverage artifact from the existing full scope.
2. Review and commit a non-regression baseline rather than inventing a target.
3. Replace the broad mypy suppression with an explicit debt inventory or narrow per-module allowlist.
4. Add Python 3.10 to the canonical exact-wheel qualification route.
5. Update this contract only with fresh command or CI evidence.

## Safety boundary

Quality progress is invalid when it is achieved by weakening tests, hiding gates, reducing assertions, or presenting an unmeasured property as proven.
