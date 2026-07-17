# C++ adoption-to-diagnosis proof

This page documents the first complete review-first C++ product vertical in SDETKit. The proof composes existing adoption-surface, FailureVector, SafetyGate, ProtectedVerifier, Doctor, trajectory, and RepoMemory contracts. It does not introduce a C++-specific control plane.

## Operator journey

```text
C++ repository detected
→ repository-owned CMake, CTest, and quality evidence identified
→ exact proof commands retained as manual recommendations
→ saved CTest and GoogleTest evidence normalized into FailureVector
→ SafetyGate and ProtectedVerifier keep the result review-first
→ Doctor reports the first meaningful failure and next human action
→ trajectory and RepoMemory retain sanitized, reporting-only evidence
```

The repository fixture is `tests/fixtures/adoption_repos/cpp_operator_proof`. The saved CI evidence is `tests/fixtures/ci_failures/cpp_ctest_operator_proof/ci_log.txt`.

## What is detected

SDETKit reads the fixture repository and reports:

- language: `cpp`, from repository-owned CMake, source, header, and test files;
- configure command: `cmake --preset ci`;
- build command: `cmake --build --preset ci`;
- test command: `ctest --preset ci`;
- explicit analysis commands for `clang-tidy`, `cppcheck`, and non-mutating `clang-format`;
- Clang/GCC address and undefined-behavior sanitizer configuration;
- CodeQL C/C++ evidence only from literal `languages: c-cpp` workflow configuration;
- compile-database ownership from explicit `CMAKE_EXPORT_COMPILE_COMMANDS` configuration.

Every command retains its repository file and working-directory context. Every command is emitted with `executes_untrusted_code=true` and `auto_run_allowed=false`.

## What is inferred

The saved CTest log is classified as:

- ecosystem: `cpp`;
- tool: `ctest_google_test`;
- failure class: `test`;
- affected file: `tests/calculator_test.cpp`;
- failing check: `Calculator.Adds`;
- exit code: `8`;
- local proof command: `ctest --preset ci`;
- confidence: `high`.

The log is read as evidence. SDETKit does not install CMake, Ninja, compilers, analyzers, formatters, sanitizers, CodeQL, GoogleTest, or CTest, and it does not run the fixture.

## What is proven

The reusable `sdetkit.cpp_operator_proof` builder verifies that the same evidence passes through shared platform contracts:

1. adoption discovery preserves repository ownership and exact advisory commands;
2. the saved log becomes a shared FailureVector;
3. SafetyGate classifies the test failure as review-first and not mechanically eligible;
4. ProtectedVerifier records a blocked review-first decision because no patch candidate or proof execution was supplied;
5. Doctor reports `review_required`, the exact failure class, and the explicit local reproduction command;
6. trajectory evidence records one review-first outcome and no safe-fix pattern;
7. RepoMemory accepts the sanitized FailureVector and SafetyGate evidence as observation-only context;
8. repository digests before and after the proof are identical;
9. deterministic JSON and Markdown artifacts are written for operator review.

ProtectedVerifier is deliberately not given a synthetic patch. The proof validates diagnosis and handoff, not remediation eligibility.

## Produced artifacts

The builder writes:

```text
cpp-operator-proof.json
cpp-operator-proof.md
doctor-report.json
doctor-report.md
safety-gate-decision.json
safety-gate-decision.md
protected-verifier-decision.json
protected-verifier-decision.md
repo-memory-profile.json
```

The top-level proof artifact includes source-evidence digests, repository before/after digests, verification checks, unsupported behavior, manual actions, and the complete authority boundary.

## Unsupported behavior

This proof does not claim support for:

- target CMake, Meson, compiler, analyzer, formatter, sanitizer, or test execution;
- dynamic workflow matrices, templates, variables, remote includes, or composite shell behavior;
- every compiler, generator, IDE, test framework, or proprietary analyzer;
- automatic source fixes, dependency changes, security dismissal, publication, or merge;
- semantic equivalence or target runtime correctness.

Unknown or mixed saved evidence remains low-confidence and review-first. Generated and vendored trees do not create repository ownership claims.

## Authority boundary

The complete vertical explicitly preserves:

```text
target_code_execution=false
auto_run_allowed=false
automation_allowed=false
patch_application_allowed=false
security_dismissal_allowed=false
publication_authorized=false
merge_authorized=false
semantic_equivalence_proven=false
```

The proof demonstrates discovery, diagnosis, safety classification, reporting, and reviewed learning. It does not authorize remediation.

## What remains manual

A human operator must still:

1. review the repository-owned commands and saved failure evidence;
2. decide whether running the exact C++ command is appropriate in the target environment;
3. inspect the affected source or test file;
4. approve any patch, build-file change, dependency change, or security disposition separately;
5. run focused and full proof after an approved change;
6. approve merge or release through the repository's normal controls.

## Reproduce the repository proof

```bash
python -m pytest -q \
  tests/test_cpp_operator_proof.py \
  tests/test_adoption_surface_cpp.py \
  tests/test_adoption_surface_cpp_quality_security.py \
  tests/test_cpp_failure_vector_adapters.py \
  -o addopts=
python -m mypy src
python -m pre_commit run -a
NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict
```

No command above executes the C++ fixture. The repository fixture and saved log remain read-only product evidence.
