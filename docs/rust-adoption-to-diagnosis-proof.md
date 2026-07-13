# Rust adoption-to-diagnosis proof

This page documents the first complete review-first Rust product vertical in SDETKit. The proof composes the existing adoption-surface, FailureVector, SafetyGate, and Doctor report contracts. It does not introduce a Rust-specific control plane.

## Operator journey

```text
Rust repository detected
→ Cargo proof surfaces identified from repository evidence
→ explicit cargo-audit evidence reported
→ saved cargo test failure normalized into FailureVector
→ SafetyGate keeps the result review-first
→ Doctor report carries the failure evidence and next human action
```

The fixture used for this proof is `tests/fixtures/adoption_repos/rust_cargo`. The saved CI evidence is `tests/fixtures/ci_failures/cargo_test/ci_log.txt`.

## What is detected

SDETKit reads repository files and reports:

- language: `rust`, from `Cargo.toml`
- package manager: `cargo`, from `Cargo.toml`
- proof command: `cargo test`
- security surface: `cargo_audit`, only because the fixture contains an explicit workflow command
- security proof command: `cargo audit`

`Cargo.toml` alone does not imply cargo-audit adoption. The security surface is emitted only when explicit workflow, script, or configuration evidence exists.

## What is inferred

The adoption surface recommends commands from repository evidence, but does not execute them. Every recommended command keeps `auto_run_allowed=false` because Cargo commands may build or execute untrusted target code.

The saved Cargo log is classified as:

- ecosystem: `rust`
- tool: `cargo_test`
- failure class: `test`
- affected file: `src/lib.rs`
- exit code: `101`
- local proof command: `cargo test`
- confidence: `high`

The log is read as evidence. SDETKit does not install Rust, run Cargo, modify `Cargo.lock`, or touch the target repository.

## What is proven

The integration proof verifies that the normalized Rust FailureVector can be passed into the existing Doctor report contract. Doctor then reports:

- status: `review_required`
- confidence: `high`
- roadmap lane: `failure_diagnosis`
- top failure check: `cargo-test`
- top failure type: `test`
- next local proof: `cargo test`

The same evidence is rendered as deterministic JSON and Markdown artifacts in the test proof.

## Authority boundary

The complete vertical explicitly preserves these values:

```text
target_code_execution=false
auto_run_allowed=false
automation_allowed=false
patch_application_allowed=false
security_dismissal_allowed=false
merge_authorized=false
semantic_equivalence_claim=false
```

This proof demonstrates diagnosis and reporting capability. It does not authorize remediation.

## What remains manual

A human operator must still:

1. review the repository and saved failure evidence;
2. decide whether running Cargo commands is appropriate in the target environment;
3. inspect the failing Rust code and test;
4. review cargo-audit findings without automatic dismissal;
5. approve any patch, dependency change, lockfile change, or merge separately.

## Reproduce the repository proof

```bash
python -m pytest -q \
  tests/test_rust_adoption_vertical.py \
  tests/test_adoption_surface_cargo_audit.py \
  tests/test_cross_ecosystem_failure_vector_adapters.py \
  tests/test_doctor_report_contract.py \
  -o addopts=
python -m mypy src
python -m pre_commit run -a
NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict
```

No command above executes the Rust fixture. The fixture and saved log remain read-only product evidence.
