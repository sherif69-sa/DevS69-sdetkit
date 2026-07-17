# Mixed-language monorepo adoption-to-diagnosis proof

SDETKit can compose one review-first operator journey across a root Python project, nested Python and JavaScript/TypeScript workspaces, and a compiled Rust workspace without executing target-repository commands.

The reusable proof lives in:

- `src/sdetkit/mixed_monorepo_operator_proof.py`
- `tests/test_mixed_monorepo_operator_proof.py`
- `tests/fixtures/adoption_repos/mixed_nested_workspaces`
- `tests/fixtures/ci_failures/mixed_monorepo`

## Operator journey

```text
repository-owned topology and manifests
→ workspace-scoped manual proof recommendations
→ saved JavaScript/TypeScript and Rust failure logs
→ workspace-owned FailureVectors
→ per-workspace SafetyGate and ProtectedVerifier evidence
→ aggregated Doctor report
→ sanitized trajectory and RepoMemory evidence
```

## Detected

The proof detects only repository-owned evidence:

- root Python ownership and its manual pytest recommendation;
- nested Python ownership in `services/api`;
- separate JavaScript/TypeScript ownership in `apps/admin` and `apps/web`;
- compiled Rust ownership in `crates/native`;
- the source manifest and working directory for each nested recommendation;
- saved failure evidence that names exactly one declared workspace.

Identical `npm test` recommendations remain separate because their source working directories and manifests differ.

## Inferred

Supported saved logs are normalized through the existing ecosystem FailureVector adapters. The adapter may infer a failure class, tool, affected file, and local reproduction command from saved evidence. Those fields remain advisory and are not proof that the command has run successfully in the target repository.

A saved log that names multiple workspaces is not assigned to either workspace. It becomes low-confidence `unknown` evidence with no local reproduction command and remains review-first.

## Proven

The fixture-backed tests prove that:

- root and nested ownership remain distinct;
- duplicate command text does not collapse workspace identity;
- generated, vendored, dependency, and build-output paths do not become high-confidence owners;
- each supported saved failure retains workspace, ecosystem, manifest, and evidence-source identity;
- SafetyGate and ProtectedVerifier remain review-first for every workspace result;
- Doctor reports the aggregated FailureVector evidence without authorizing action;
- trajectory and RepoMemory retain sanitized observation-only evidence;
- serialized JSON and Markdown are deterministic;
- the target fixture digest is unchanged before and after proof generation.

## Artifacts

The proof writes deterministic artifacts to the selected output directory:

```text
mixed-monorepo-operator-proof.json
mixed-monorepo-operator-proof.md
workspace-failures.json
doctor-report.json
doctor-report.md
repo-memory-profile.json
```

The CLI prints only a sanitized completion manifest. Detailed repository and failure evidence remains in the explicit output files.

## Unsupported and manual

SDETKit does not resolve dynamic CI templates, matrices, variables, remote includes, generated commands, or proprietary build behavior in this proof. It does not install package managers, compilers, test runners, or dependencies.

An operator must review the detected workspace and saved evidence, decide which repository-owned command is safe to run in a trusted environment, approve any proposed change separately, and rerun focused and full proof after remediation.

## Authority boundary

```text
target_code_execution=false
automation_allowed=false
patch_application_allowed=false
security_dismissal_allowed=false
publication_authorized=false
merge_authorized=false
semantic_equivalence_proven=false
```

Discovery, diagnosis, verification, reporting, and memory evidence do not grant mutation or merge authority.
