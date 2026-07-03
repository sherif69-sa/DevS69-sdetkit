# Quality truth baseline

SDETKit uses staged quality gates. This page records what is enforced today, what is measured, and what remains incomplete so a green check cannot be interpreted more broadly than the evidence supports.

Contract: [`docs/contracts/quality-truth-baseline.v1.json`](contracts/quality-truth-baseline.v1.json)

Validator:

```bash
python scripts/check_quality_truth_baseline.py \
  --out build/quality/quality-truth-check.json \
  --typing-debt-out build/quality/typing-debt-inventory.json
```

## Coverage truth

Fresh CI evidence at PR #1929 measured:

- critical reliability spine: **96.69%** across **966** statements;
- whole package: **87.89%** across **66,030** statements.

The critical spine retains a 95% minimum. The whole-package result is now a reviewed non-regression baseline: future Quality runs fail when measured package coverage drops below 87.89%, while still reporting the exact current result.

The workflow emits:

```text
build/quality/coverage-full.json
build/quality/coverage-truth-check.json
```

The repository must not describe the whole package as 95% covered. The 95% statement applies only to the declared critical reliability spine.

## Typing truth

The repository still has a broad `sdetkit.*` mypy suppression. Nineteen diagnostic, safety, trajectory, adoption, and proof modules explicitly opt back into error checking.

The reviewed inventory after adding the evidence-binding module records:

```text
source_module_count=498
explicitly_type_checked_module_count=19
typing_debt_module_count=479
```

The complete debt module list is emitted to:

```text
build/quality/typing-debt-inventory.json
```

Its sorted module list is hash-bound in the contract. Adding, removing, or moving a source module changes the count or digest and requires an explicit baseline review. New production modules cannot inherit unrecorded typing debt without changing a reviewed contract.

This remains a migration state, not a completion claim:

```text
blanket_package_suppression_present=true
migration_complete=false
new_unrecorded_suppression_allowed=false
```

## Runtime truth

The package metadata declares Python 3.10, 3.11, and 3.12. Canonical fast and smoke CI currently cover Python 3.11 and 3.12. Python 3.10 appears in the first-proof route, but exact-wheel qualification across all three versions remains release work.

## Required next steps

1. Reduce the hashed 479-module typing-debt inventory through behavior-focused ratchets.
2. Keep whole-package coverage at or above the reviewed 87.89% baseline.
3. Keep the critical reliability spine at or above 95%.
4. Add Python 3.10 to the exact-wheel qualification route.
5. Update this contract only with fresh command or CI evidence.

## Safety boundary

Quality progress is invalid when it is achieved by weakening tests, hiding gates, reducing assertions, or presenting an unmeasured property as proven.
